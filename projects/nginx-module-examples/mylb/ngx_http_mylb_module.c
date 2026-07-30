/*
 * ngx_http_mylb_module — 负载均衡器模块示例（可编译、可运行）
 *
 * 功能：在 upstream {} 中写 `mylb;` 启用自定义选节点算法（这里演示简单轮转）。
 *
 * 实现要点（对照 round-robin 官方范式）：
 *   - postconfiguration 阶段把启用了 mylb 的 upstream 的
 *     us->peer.init 指向本模块的 per-request init 函数；
 *   - 该 init 函数（签名 ngx_http_upstream_init_peer_pt）在每次请求时执行，
 *     从 us->servers 取节点列表，存入 r->upstream->peer.data，
 *     并设置 r->upstream->peer.get / .free 回调；
 *   - get_peer（签名 ngx_http_upstream_get_peer_pt）做轮转选择并填 pc；
 *   - free_peer（签名 ngx_http_upstream_free_peer_pt）处理失败重试。
 *
 * 对应文档：[[entities/Nginx 模块开发实战]] §5 / [[concepts/Nginx 框架内部实现]] §11
 */
#include <ngx_config.h>
#include <ngx_core.h>
#include <ngx_http.h>

typedef struct {
    ngx_uint_t  current;     /* 轮转游标（per upstream srv_conf） */
} ngx_http_mylb_srv_conf_t;

typedef struct {
    ngx_http_upstream_server_t *servers;   /* 该 upstream 的 server 列表 */
    ngx_uint_t                  nservers;
    ngx_uint_t                 *current;    /* 指向 srv_conf 的游标 */
} ngx_http_mylb_peer_data_t;

static ngx_int_t ngx_http_mylb_init_peer(ngx_http_request_t *r,
                                         ngx_http_upstream_srv_conf_t *us);
static ngx_int_t ngx_http_mylb_get_peer(ngx_peer_connection_t *pc, void *data);
static void      ngx_http_mylb_free_peer(ngx_peer_connection_t *pc, void *data,
                                         ngx_uint_t state);
static ngx_int_t ngx_http_mylb_postconfiguration(ngx_conf_t *cf);
static void     *ngx_http_mylb_create_srv_conf(ngx_conf_t *cf);
static char     *ngx_http_mylb_set(ngx_conf_t *cf, ngx_command_t *cmd, void *conf);

static ngx_command_t ngx_http_mylb_commands[] = {
    { ngx_string("mylb"),
      NGX_HTTP_UPS_CONF | NGX_CONF_NOARGS,
      ngx_http_mylb_set,                  /* 标记指令：仅置位，真正接管在 init */
      NGX_HTTP_SRV_CONF_OFFSET,
      0,
      NULL },
    ngx_null_command
};

static ngx_http_module_t ngx_http_mylb_module_ctx = {
    NULL,                                       /* preconfiguration */
    ngx_http_mylb_postconfiguration,            /* postconfiguration */
    NULL,                                       /* create main conf */
    NULL,                                       /* init main conf */
    ngx_http_mylb_create_srv_conf,              /* create server conf */
    NULL,                                       /* merge server conf */
    NULL,                                       /* create location conf */
    NULL                                        /* merge location conf */
};

ngx_module_t ngx_http_mylb_module = {
    NGX_MODULE_V1,
    &ngx_http_mylb_module_ctx,
    ngx_http_mylb_commands,
    NGX_HTTP_MODULE,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NGX_MODULE_V1_PADDING
};

/* 标记指令：只返回 OK（真正挂接在 postconfiguration 阶段完成） */
static char *
ngx_http_mylb_set(ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    return NGX_CONF_OK;
}

static void *
ngx_http_mylb_create_srv_conf(ngx_conf_t *cf)
{
    ngx_http_mylb_srv_conf_t *conf;

    conf = ngx_pcalloc(cf->pool, sizeof(ngx_http_mylb_srv_conf_t));
    if (conf == NULL) {
        return NULL;
    }
    conf->current = 0;
    return conf;
}

/* postconfiguration：把配置了 mylb 的 upstream 接管 us->peer.init */
static ngx_int_t
ngx_http_mylb_postconfiguration(ngx_conf_t *cf)
{
    ngx_http_upstream_main_conf_t *umcf;
    ngx_http_upstream_srv_conf_t **uscfp;
    ngx_uint_t i;

    umcf = ngx_http_conf_get_module_main_conf(cf, ngx_http_upstream_module);
    uscfp = umcf->upstreams.elts;

    for (i = 0; i < umcf->upstreams.nelts; i++) {
        if (uscfp[i]->servers == NULL || uscfp[i]->servers->nelts == 0) {
            continue;
        }
        ngx_http_mylb_srv_conf_t *scf =
            uscfp[i]->srv_conf[ngx_http_mylb_module.ctx_index];
        if (scf == NULL) {
            continue;
        }
        /* 接管 per-request 初始化（选节点回调在 init_peer 里挂） */
        uscfp[i]->peer.init = ngx_http_mylb_init_peer;
    }

    return NGX_OK;
}

/* per-request init_peer：设置 get/free 并准备 peer data */
static ngx_int_t
ngx_http_mylb_init_peer(ngx_http_request_t *r, ngx_http_upstream_srv_conf_t *us)
{
    ngx_http_mylb_srv_conf_t *scf =
        us->srv_conf[ngx_http_mylb_module.ctx_index];

    ngx_http_mylb_peer_data_t *pd =
        ngx_pcalloc(r->pool, sizeof(ngx_http_mylb_peer_data_t));
    if (pd == NULL) {
        return NGX_ERROR;
    }

    pd->servers  = us->servers->elts;
    pd->nservers = us->servers->nelts;
    pd->current  = &scf->current;

    /* 关键：把选节点回调挂到本次请求的 peer 连接上 */
    r->upstream->peer.data = pd;
    r->upstream->peer.get  = ngx_http_mylb_get_peer;
    r->upstream->peer.free = ngx_http_mylb_free_peer;

    return NGX_OK;
}

/* get_peer：轮转选一个 server 填入 pc */
static ngx_int_t
ngx_http_mylb_get_peer(ngx_peer_connection_t *pc, void *data)
{
    ngx_http_mylb_peer_data_t *pd = data;

    if (pd == NULL || pd->nservers == 0) {
        return NGX_ERROR;
    }

    ngx_uint_t idx = (*pd->current) % pd->nservers;
    ngx_http_upstream_server_t *s = &pd->servers[idx];
    (*pd->current) = (idx + 1) % pd->nservers;

    pc->sockaddr = s->addrs[0].sockaddr;
    pc->socklen  = s->addrs[0].socklen;
    pc->name     = &s->addrs[0].name;

    pc->tries   = pd->nservers;     /* 允许在节点不可达时重试其它节点 */
    return NGX_OK;
}

static void
ngx_http_mylb_free_peer(ngx_peer_connection_t *pc, void *data, ngx_uint_t state)
{
    ngx_http_mylb_peer_data_t *pd = data;

    /* state 含 NGX_PEER_FAILED 时表示本次连接失败。
       轮转游标已在 get_peer 推进；生产可在此维护故障标记表。
       注意：不要在这里改 pc->tries（框架据此决定是否重试）。 */
    ngx_log_debug1(NGX_LOG_DEBUG_HTTP, pc->log, 0,
                   "mylb free peer state:%ui", state);
    (void) pd;
}
