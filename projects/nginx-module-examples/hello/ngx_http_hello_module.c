/*
 * ngx_http_hello_module — 最小可编译 Handler 模块
 *
 * 功能：在 location 中写 `hello;` 后，访问该 location 返回 "Hello from nginx module!".
 * 编译：作为动态模块 (--add-dynamic-module=.../hello) 或静态模块 (--add-module=.../hello)。
 *
 * 对应文档：[[entities/Nginx 模块开发实战]] §2 / [[concepts/Nginx 框架内部实现]] §2,§7
 */
#include <ngx_config.h>
#include <ngx_core.h>
#include <ngx_http.h>

static ngx_int_t ngx_http_hello_handler(ngx_http_request_t *r);
static char      *ngx_http_hello_set(ngx_conf_t *cf, ngx_command_t *cmd, void *conf);

static ngx_command_t ngx_http_hello_commands[] = {

    { ngx_string("hello"),
      NGX_HTTP_LOC_CONF | NGX_CONF_NOARGS,
      ngx_http_hello_set,
      NGX_HTTP_LOC_CONF_OFFSET,
      0,
      NULL },

      ngx_null_command
};

static ngx_http_module_t ngx_http_hello_module_ctx = {
    NULL,  /* preconfiguration */
    NULL,  /* postconfiguration */
    NULL,  /* create main conf */
    NULL,  /* init main conf */
    NULL,  /* create server conf */
    NULL,  /* merge server conf */
    NULL,  /* create location conf */
    NULL   /* merge location conf */
};

ngx_module_t ngx_http_hello_module = {
    NGX_MODULE_V1,
    &ngx_http_hello_module_ctx,
    ngx_http_hello_commands,
    NGX_HTTP_MODULE,
    NULL,  /* init master */
    NULL,  /* init module */
    NULL,  /* init process */
    NULL,  /* init thread */
    NULL,  /* exit thread */
    NULL,  /* exit process */
    NULL,  /* exit master */
    NGX_MODULE_V1_PADDING
};

/* location 指令回调：把本模块挂到 content 阶段 */
static char *
ngx_http_hello_set(ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    ngx_http_core_loc_conf_t *clcf =
        ngx_http_conf_get_module_loc_conf(cf, ngx_http_core_module);

    clcf->handler = ngx_http_hello_handler;
    return NGX_CONF_OK;
}

static ngx_int_t
ngx_http_hello_handler(ngx_http_request_t *r)
{
    static const u_char body[] = "Hello from nginx module!\n";

    r->headers_out.status = NGX_HTTP_OK;
    r->headers_out.content_type.len  = sizeof("text/plain") - 1;
    r->headers_out.content_type.data = (u_char *) "text/plain";
    r->headers_out.content_length_n = sizeof(body) - 1;

    ngx_http_send_header(r);

    ngx_buf_t *b = ngx_pcalloc(r->pool, sizeof(ngx_buf_t));
    if (b == NULL) {
        return NGX_HTTP_INTERNAL_SERVER_ERROR;
    }

    b->start = (u_char *) body;
    b->pos   = (u_char *) body;
    b->end   = b->pos + sizeof(body) - 1;
    b->last  = b->end;
    b->last_buf = (r == r->main) ? 1 : 0;
    b->memory   = 1;    /* 内容在常量区，只读 */

    ngx_chain_t out = { b, NULL };
    return ngx_http_output_filter(r, &out);
}
