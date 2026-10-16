#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ipc.h>
#include <sys/shm.h>
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/extensions/XShm.h>

/*
 * X11 MIT-SHM 捕获上下文结构体。
 */
typedef struct {
    Display *display;
    XShmSegmentInfo shminfo;
    XImage *image;
    int width;
    int height;
    int depth;
    int stride;
    unsigned char *buffer;
} XShmContext;

/*
 * 初始化 XShm 共享内存段及 XImage 缓冲区。
 * @param dpy     X11 Display 指针
 * @param screen  屏幕编号
 * @param width   捕获区域宽度
 * @param height  捕获区域高度
 * @return 成功返回 XShmContext 指针，失败返回 NULL
 */
XShmContext* xshm_init(Display *dpy, int screen, int width, int height) {
    if (!dpy || width <= 0 || height <= 0) {
        return NULL;
    }

    XShmContext *ctx = (XShmContext*)calloc(1, sizeof(XShmContext));
    if (!ctx) {
        return NULL;
    }

    ctx->display = dpy;
    ctx->width = width;
    ctx->height = height;

    Visual *visual = DefaultVisual(dpy, screen);
    ctx->depth = DefaultDepth(dpy, screen);

    ctx->image = XShmCreateImage(dpy, visual, ctx->depth, ZPixmap, NULL, &ctx->shminfo, width, height);
    if (!ctx->image) {
        free(ctx);
        return NULL;
    }

    /* 分配并映射共享内存段 */
    int shm_size = ctx->image->bytes_per_line * ctx->image->height;
    ctx->shminfo.shmid = shmget(IPC_PRIVATE, shm_size, IPC_CREAT | 0777);
    if (ctx->shminfo.shmid < 0) {
        ctx->image->data = NULL;
        XDestroyImage(ctx->image);
        free(ctx);
        return NULL;
    }

    ctx->shminfo.shmaddr = ctx->image->data = (char*)shmat(ctx->shminfo.shmid, 0, 0);
    if (ctx->shminfo.shmaddr == (char*)-1) {
        shmctl(ctx->shminfo.shmid, IPC_RMID, 0);
        ctx->image->data = NULL;
        XDestroyImage(ctx->image);
        free(ctx);
        return NULL;
    }
    ctx->shminfo.readOnly = False;

    /* 将共享内存段附加到 X 服务端 */
    if (!XShmAttach(dpy, &ctx->shminfo)) {
        shmdt(ctx->shminfo.shmaddr);
        shmctl(ctx->shminfo.shmid, IPC_RMID, 0);
        ctx->image->data = NULL;
        XDestroyImage(ctx->image);
        free(ctx);
        return NULL;
    }

    XSync(dpy, False);
    shmctl(ctx->shminfo.shmid, IPC_RMID, 0);

    ctx->stride = ctx->image->bytes_per_line;
    ctx->buffer = (unsigned char*)ctx->shminfo.shmaddr;
    return ctx;
}

static int g_xshm_error = 0;

/*
 * X11 错误事件捕获回调。
 */
static int xshm_error_handler(Display *dpy, XErrorEvent *ev) {
    (void)dpy;
    (void)ev;
    g_xshm_error = 1;
    return 0;
}

/*
 * 从指定 X11 窗口抓取图像到共享内存缓冲区。
 * @param ctx        XShm 上下文指针
 * @param win        目标窗口 XID
 * @param x          起始横坐标
 * @param y          起始纵坐标
 * @param out_buf    输出图像数据首地址指针
 * @param out_stride 输出行跨度（字节）
 * @return 成功返回 1，失败返回 0
 */
int xshm_capture(XShmContext *ctx, Window win, int x, int y, unsigned char **out_buf, int *out_stride) {
    if (!ctx || !ctx->display || !ctx->image) {
        return 0;
    }

    g_xshm_error = 0;
    XErrorHandler prev_handler = XSetErrorHandler(xshm_error_handler);

    Status st = XShmGetImage(ctx->display, win, ctx->image, x, y, AllPlanes);
    XSync(ctx->display, False);

    XSetErrorHandler(prev_handler);

    if (!st || g_xshm_error) {
        return 0;
    }

    if (out_buf) {
        *out_buf = ctx->buffer;
    }
    if (out_stride) {
        *out_stride = ctx->stride;
    }
    return 1;
}

/*
 * 释放 XShm 上下文关联的共享内存及 XImage 资源。
 * @param ctx XShm 上下文指针
 */
void xshm_destroy(XShmContext *ctx) {
    if (!ctx) {
        return;
    }

    if (ctx->display && ctx->image) {
        XErrorHandler prev_handler = XSetErrorHandler(xshm_error_handler);
        XShmDetach(ctx->display, &ctx->shminfo);
        XSync(ctx->display, False);
        XSetErrorHandler(prev_handler);

        ctx->image->data = NULL;
        XDestroyImage(ctx->image);
        if (ctx->shminfo.shmaddr && ctx->shminfo.shmaddr != (char*)-1) {
            shmdt(ctx->shminfo.shmaddr);
        }
    }
    free(ctx);
}
