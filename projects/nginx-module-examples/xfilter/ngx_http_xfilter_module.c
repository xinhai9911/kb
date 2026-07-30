/*
 * ngx_http_xfilter_module — Filter 模块示例
 *
 * 功能：给所有响应加一个自定义响应头  X-Powered-By: ngx-xfilter
 *       体过滤器透传（可在此做替换/压缩）。
 * 要点：必须调用链上下一个 filter (ngx_http_next_*_filter)，否则响应断流。
 *
 * 对应文档：[[entities/Nginx 模块开发实战]] §3 / [[concepts/Nginx 框架内部实现]] §11
 */
#include <ngx_config.h>
#include <ngx_core.h>
#include <ngx_http.h>

static ngx_int_t ngx_http_xfilter_header_filter(ngx_http_request_t *r);
static ngx_int_t ngx_http_xfilter_body_filter(ngx_http_request_t *r, ngx_chain_t *in);
static ngx_int_t ngx_http_xfilter_postconfiguration(ngx_conf_t *cf);

static ngx_http_output_header_filter_pt ngx_http_next_header_filter;
static ngx_http_output_body_filter_pt   ngx_http_next_body_filter;

static ngx_http_module_t ngx_http_xfilter_module_ctx = {
    NULL,                                     /* preconfiguration */
    ngx_http_xfilter_postconfiguration,       /* postconfiguration */
    NULL, NULL, NULL, NULL, NULL, NULL
};

ngx_module_t ngx_http_xfilter_module = {
    NGX_MODULE_V1,
    &ngx_http_xfilter_module_ctx,
    NULL,                       /* 本例无需自定义指令 */
    NGX_HTTP_MODULE,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NGX_MODULE_V1_PADDING
};

static ngx_int_t
ngx_http_xfilter_postconfiguration(ngx_conf_t *cf)
{
    ngx_http_next_header_filter = ngx_http_top_header_filter;
    ngx_http_top_header_filter  = ngx_http_xfilter_header_filter;

    ngx_http_next_body_filter   = ngx_http_top_body_filter;
    ngx_http_top_body_filter    = ngx_http_xfilter_body_filter;
    return NGX_OK;
}

static ngx_int_t
ngx_http_xfilter_header_filter(ngx_http_request_t *r)
{
    ngx_table_elt_t *h;

    h = ngx_list_push(&r->headers_out.headers);
    if (h) {
        h->hash = 1;
        ngx_str_set(&h->key, "X-Powered-By");
        ngx_str_set(&h->value, "ngx-xfilter");
    }

    return ngx_http_next_header_filter(r);
}

static ngx_int_t
ngx_http_xfilter_body_filter(ngx_http_request_t *r, ngx_chain_t *in)
{
    /* 想替换/压缩 body：在此遍历 in 链，对 ngx_buf_t 处理后再重组 chain。
       本例直接透传。 */
    return ngx_http_next_body_filter(r, in);
}
