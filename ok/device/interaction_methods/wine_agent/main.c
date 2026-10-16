#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <stdint.h>
#include <stdio.h>
#include <stdbool.h>

/* 通信协议常量与指令标识 */
#define AGENT_MAGIC 0x4F4B5757  /* "OKWW" */
#define DEFAULT_PORT 49152

#define CMD_POST_MSG   1
#define CMD_PING       2
#define CMD_SET_HWND   3
#define CMD_EXIT       4

#pragma pack(push, 1)
/*
 * IPC 控制协议请求数据包结构（紧凑单字节对齐）。
 */
typedef struct {
    uint32_t magic;
    uint32_t cmd;
    uint64_t hwnd;
    uint32_t msg;
    uint64_t wparam;
    int64_t  lparam;
} OkMsgPacket;

/*
 * IPC 控制协议响应数据包结构。
 */
typedef struct {
    uint32_t magic;
    int32_t  status;
    uint64_t hwnd;
} OkMsgResponse;
#pragma pack(pop)

static HWND g_target_hwnd = NULL;

/*
 * 枚举顶级窗口回调，匹配指定类名或标题的目标窗口。
 * @param hwnd   当前遍历的窗口句柄
 * @param lParam 输出窗口句柄指针
 * @return 找到目标窗口返回 FALSE 终止枚举，否则返回 TRUE 继续遍历
 */
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

/*
 * 查找目标游戏窗口句柄。
 * @return 成功返回窗口 HWND，未找到返回 NULL
 */
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

/*
 * 客户端连接处理线程，循环解析协议数据包并分发 Win32 消息。
 * @param param 客户端套接字描述符
 * @return 线程退出状态码 0
 */
static DWORD WINAPI ClientWorkerThread(LPVOID param) {
    SOCKET client_sock = (SOCKET)(uintptr_t)param;
    BOOL keepalive = TRUE;
    setsockopt(client_sock, SOL_SOCKET, SO_KEEPALIVE, (const char*)&keepalive, sizeof(keepalive));

    while (1) {
        OkMsgPacket pkt;
        int total_read = 0;
        /* 完整读取定长协议请求包 */
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
            /* 执行 PostMessage 消息投递 */
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

/*
 * Wine 代理守护进程入口，初始化 TCP 服务并监听本地回环端口。
 * @param argc 参数个数
 * @param argv 参数列表，支持通过 argv[1] 指定监听端口号
 * @return 进程退出码
 */
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
