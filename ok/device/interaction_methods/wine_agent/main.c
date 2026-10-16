#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <stdint.h>
#include <stdio.h>
#include <stdbool.h>

#define AGENT_MAGIC 0x4F4B5757  /* "OKWW" */
#define DEFAULT_PORT 49152

#define CMD_POST_MSG   1
#define CMD_PING       2
#define CMD_SET_HWND   3
#define CMD_EXIT       4

#pragma pack(push, 1)
typedef struct {
    uint32_t magic;
    uint32_t cmd;
    uint64_t hwnd;
    uint32_t msg;
    uint64_t wparam;
    int64_t  lparam;
} OkMsgPacket;

typedef struct {
    uint32_t magic;
    int32_t  status;
    uint64_t hwnd;
} OkMsgResponse;
#pragma pack(pop)

static HWND g_target_hwnd = NULL;

static BOOL CALLBACK EnumWindowsProc(HWND hwnd, LPARAM lParam) {
    if (!IsWindowVisible(hwnd)) {
        return TRUE;
    }
    wchar_t title[256] = {0};
    wchar_t cls[256] = {0};
    GetWindowTextW(hwnd, title, 255);
    GetClassNameW(hwnd, cls, 255);

    if (wcsstr(cls, L"UnrealWindow") != NULL ||
        wcsstr(title, L"鸣潮") != NULL ||
        wcsstr(title, L"Wuthering Waves") != NULL ||
        wcsstr(title, L"Client-Win64-Shipping") != NULL) {
        *(HWND*)lParam = hwnd;
        return FALSE;
    }
    return TRUE;
}

static HWND FindTargetGameWindow(void) {
    if (g_target_hwnd && IsWindow(g_target_hwnd)) {
        return g_target_hwnd;
    }
    HWND found = FindWindowW(L"UnrealWindow", NULL);
    if (!found) {
        EnumWindows(EnumWindowsProc, (LPARAM)&found);
    }
    if (found) {
        g_target_hwnd = found;
    }
    return found;
}

static DWORD WINAPI ClientWorkerThread(LPVOID param) {
    SOCKET client_sock = (SOCKET)(uintptr_t)param;
    BOOL keepalive = TRUE;
    setsockopt(client_sock, SOL_SOCKET, SO_KEEPALIVE, (const char*)&keepalive, sizeof(keepalive));

    while (1) {
        OkMsgPacket pkt;
        int total_read = 0;
        while (total_read < (int)sizeof(pkt)) {
            int r = recv(client_sock, ((char*)&pkt) + total_read, sizeof(pkt) - total_read, 0);
            if (r <= 0) {
                break;
            }
            total_read += r;
        }

        if (total_read != sizeof(pkt) || pkt.magic != AGENT_MAGIC) {
            break;
        }

        OkMsgResponse resp;
        resp.magic = AGENT_MAGIC;
        resp.status = 0;
        resp.hwnd = (uint64_t)(uintptr_t)g_target_hwnd;

        if (pkt.cmd == CMD_PING) {
            FindTargetGameWindow();
            resp.hwnd = (uint64_t)(uintptr_t)g_target_hwnd;
            send(client_sock, (const char*)&resp, sizeof(resp), 0);
        } else if (pkt.cmd == CMD_SET_HWND) {
            g_target_hwnd = (HWND)(uintptr_t)pkt.hwnd;
            resp.hwnd = (uint64_t)(uintptr_t)g_target_hwnd;
            send(client_sock, (const char*)&resp, sizeof(resp), 0);
        } else if (pkt.cmd == CMD_POST_MSG) {
            HWND target = (pkt.hwnd != 0) ? (HWND)(uintptr_t)pkt.hwnd : FindTargetGameWindow();
            if (target && IsWindow(target)) {
                if (pkt.msg == WM_ACTIVATE) {
                    PostMessageW(target, WM_ACTIVATEAPP, TRUE, 0);
                    PostMessageW(target, WM_NCACTIVATE, TRUE, 0);
                    PostMessageW(target, WM_ACTIVATE, (WPARAM)pkt.wparam, (LPARAM)pkt.lparam);
                    PostMessageW(target, WM_SETFOCUS, 0, 0);
                } else {
                    PostMessageW(target, pkt.msg, (WPARAM)pkt.wparam, (LPARAM)pkt.lparam);
                }
                resp.status = 0;
                resp.hwnd = (uint64_t)(uintptr_t)target;
            } else {
                resp.status = -2;
            }
            send(client_sock, (const char*)&resp, sizeof(resp), 0);
        } else if (pkt.cmd == CMD_EXIT) {
            send(client_sock, (const char*)&resp, sizeof(resp), 0);
            closesocket(client_sock);
            ExitProcess(0);
        }
    }

    closesocket(client_sock);
    return 0;
}

int main(int argc, char** argv) {
    int port = DEFAULT_PORT;
    if (argc > 1) {
        int p = atoi(argv[1]);
        if (p > 1024 && p < 65536) {
            port = p;
        }
    }

    WSADATA wsaData;
    if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
        return 1;
    }

    SOCKET listen_sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (listen_sock == INVALID_SOCKET) {
        WSACleanup();
        return 1;
    }

    BOOL optval = TRUE;
    setsockopt(listen_sock, SOL_SOCKET, SO_REUSEADDR, (const char*)&optval, sizeof(optval));

    struct sockaddr_in server_addr;
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = inet_addr("127.0.0.1");
    server_addr.sin_port = htons((u_short)port);

    if (bind(listen_sock, (struct sockaddr*)&server_addr, sizeof(server_addr)) == SOCKET_ERROR) {
        closesocket(listen_sock);
        WSACleanup();
        return 1;
    }

    if (listen(listen_sock, SOMAXCONN) == SOCKET_ERROR) {
        closesocket(listen_sock);
        WSACleanup();
        return 1;
    }

    FindTargetGameWindow();

    while (1) {
        struct sockaddr_in client_addr;
        int client_len = sizeof(client_addr);
        SOCKET client_sock = accept(listen_sock, (struct sockaddr*)&client_addr, &client_len);
        if (client_sock == INVALID_SOCKET) {
            break;
        }

        HANDLE hThread = CreateThread(NULL, 0, ClientWorkerThread, (LPVOID)(uintptr_t)client_sock, 0, NULL);
        if (hThread) {
            CloseHandle(hThread);
        } else {
            closesocket(client_sock);
        }
    }

    closesocket(listen_sock);
    WSACleanup();
    return 0;
}
