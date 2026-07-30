/*
 * ngx_http_myupstream_module — Upstream 模块示例
 *
 * 功能：content 阶段把请求转给一个 TCP 后端，发送 "GET <uri>\r\n"，
 *       解析后端响应头（以 "OK" 开头视为 200，否则 502）。
 * 核心：必须实现 process_header 状态机，正确返回 NGX_AGAIN / NGX_OK。
 *
 * 对应文档：[[entities/Nginx 模块开发实战]] §4 / [[concepts/Nginx 框架内部实现]] §9
 */
#include <ngx_config.h>
#include <ngx_core.h>
#include <ngx_http.h>

typedef struct {
    ngx_http_upstream_conf_t  upstream;
    ngx_str_t                 backend_uri;
} ngx_http_myupstream_loc_conf_t;

static ngx_int_t ngx_http_myupstream_handler(ngx_http_request_t *r);
static ngx_int_t ngx_http_myupstream_create_request(ngx_http_request_t *r);
static ngx_int_t ngx_http_myupstream_process_header(ngx_http_request_t *r);
static void      ngx_http_myupstream_abort_request(ngx_http_request_t *r);
static void      ngx_http_myupstream_finalize_request(ngx_http_request_t *r, ngx_int_t rc);

static ngx_int_t ngx_http_myupstream_create_loc_conf(ngx_conf_t *cf);
static char     *ngx_http_myupstream_merge_loc_conf(ngx_conf_t *cf, void *parent, void *child);
static char     *ngx_http_myupstream_set(ngx_conf_t *cf, ngx_command_t *cmd, void *conf);

static ngx_command_t ngx_http_myupstream_commands[] = {

    { ngx_string("myupstream"),
      NGX_HTTP_LOC_CONF | NGX_CONF_NOARGS,
      ngx_http_myupstream_set,
      NGX_HTTP_LOC_CONF_OFFSET,
      0,
      NULL },

      ngx_null_command
};

static ngx_http_module_t ngx_http_myupstream_module_ctx = {
    NULL,                                          /* preconfiguration */
    NULL,                                          /* postconfiguration */
    NULL,                                          /* create main conf */
    NULL,                                          /* init main conf */
    NULL,                                          /* create server conf */
    NULL,                                          /* merge server conf */
    ngx_http_myupstream_create_loc_conf,           /* create location conf */
    ngx_http_myupstream_merge_loc_conf             /* merge location conf */
};

ngx_module_t ngx_http_myupstream_module = {
    NGX_MODULE_V1,
    &ngx_http_myupstream_module_ctx,
    ngx_http_myupstream_commands,
    NGX_HTTP_MODULE,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NGX_MODULE_V1_PADDING
};

static ngx_int_t
ngx_http_myupstream_create_loc_conf(ngx_conf_t *cf)
{
    ngx_http_myupstream_loc_conf_t *conf;

    conf = ngx_pcalloc(cf->pool, sizeof(ngx_http_myupstream_loc_conf_t));
    if (conf == NULL) {
        return NULL;
    }
    conf->backend_uri.data = NULL;
    conf->backend_uri.len  = 0;

    /* upstream 配置用 unset 哨兵，merge 阶段再确定 */
    conf->upstream.upstream = NGX_CONF_UNSET_PTR;

    return conf;
}

static char *
ngx_http_myupstream_merge_loc_conf(ngx_conf_t *cf, void *parent, void *child)
{
    ngx_http_myupstream_loc_conf_t *prev = parent;
    ngx_http_myupstream_loc_conf_t *conf = child;

    ngx_conf_merge_str_value(conf->backend_uri, prev->backend_uri, "/");

    if (conf->upstream.upstream == NGX_CONF_UNSET_PTR) {
        conf->upstream.upstream = prev->upstream.upstream;
    }

    return NGX_CONF_OK;
}

static char *
ngx_http_myupstream_set(ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    ngx_http_core_loc_conf_t *clcf =
        ngx_http_conf_get_module_loc_conf(cf, ngx_http_core_module);

    clcf->handler = ngx_http_myupstream_handler;
    return NGX_CONF_OK;
}

static ngx_int_t
ngx_http_myupstream_handler(ngx_http_request_t *r)
{
    ngx_http_myupstream_loc_conf_t *lcf =
        ngx_http_get_module_loc_conf(r, ngx_http_myupstream_module);

    ngx_http_upstream_t *u = ngx_http_upstream_create(r);
    if (u == NULL) {
        return NGX_HTTP_INTERNAL_SERVER_ERROR;
    }

    u->conf = &lcf->upstream;
    u->create_request  = ngx_http_myupstream_create_request;
    u->process_header  = ngx_http_myupstream_process_header;
    u->abort_request   = ngx_http_myupstream_abort_request;
    u->finalize_request = ngx_http_myupstream_finalize_request;

    r->main->count++;
    ngx_http_upstream_init(r);

    return NGX_DONE;
}

static ngx_int_t
ngx_http_myupstream_create_request(ngx_http_request_t *r)
{
    ngx_buf_t *b = ngx_create_temp_buf(r->pool, 64);
    if (b == NULL) {
        return NGX_ERROR;
    }

    b->last = ngx_sprintf(b->last, "GET %V\r\n", &r->uri);

    r->upstream->request_bufs = ngx_alloc_chain_link(r->pool);
    if (r->upstream->request_bufs == NULL) {
        return NGX_ERROR;
    }
    r->upstream->request_bufs->buf  = b;
    r->upstream->request_bufs->next = NULL;

    return NGX_OK;
}

static ngx_int_t
ngx_http_myupstream_process_header(ngx_http_request_t *r)
{
    ngx_http_upstream_t *u = r->upstream;

    /* 头未收全：移动 pos 等待更多数据 */
    if ((size_t) (u->buffer.last - u->buffer.pos) < 2) {
        return NGX_AGAIN;
    }

    if (ngx_strncmp(u->buffer.pos, "OK", 2) == 0) {
        u->headers_in.status_n = 200;
        u->headers_in.content_length_n = 0;
        return NGX_OK;
    }

    u->headers_in.status_n = 502;
    return NGX_OK;
}

static void
ngx_http_myupstream_abort_request(ngx_http_request_t *r)
{
    ngx_log_debug0(NGX_LOG_DEBUG_HTTP, r->connection->log, 0,
                   "myupstream abort request");
}

static void
ngx_http_myupstream_finalize_request(ngx_http_request_t *r, ngx_int_t rc)
{
    ngx_log_debug1(NGX_LOG_DEBUG_HTTP, r->connection->log, 0,
                   "myupstream finalize request rc:%i", rc);
}
