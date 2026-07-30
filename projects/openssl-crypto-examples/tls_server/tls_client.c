/*
 * tls_client.c — 最小 TLS 1.3 客户端（阻塞式）
 *
 * 配合 tls_server.c。演示：SSL_connect 握手 + 主机名/SNI + 证书校验。
 * 自签证书需关闭校验或将 CA 加入信任库（演示用 SSL_set_verify 关闭，
 * 生产必须开启，见 [[entities/证书与 X.509 公钥基础设施实战]]）。
 *
 * 编译：见 ../scripts/build.sh
 * 运行：./tls_client 127.0.0.1 4433
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <openssl/ssl.h>
#include <openssl/err.h>

int main(int argc, char **argv)
{
    const char *host = argc > 1 ? argv[1] : "127.0.0.1";
    int port = argc > 2 ? atoi(argv[2]) : 4433;

    SSL_load_error_strings();
    OpenSSL_add_ssl_algorithms();
    SSL_CTX *ctx = SSL_CTX_new(TLS_client_method());
    if (!ctx) { ERR_print_errors_fp(stderr); return 1; }
    SSL_CTX_set_min_proto_version(ctx, TLS1_3_VERSION);

    /* 演示：关闭校验以便连自签证书。生产务必删除下面两行并加载 CA */
    SSL_CTX_set_verify(ctx, SSL_VERIFY_NONE, NULL);

    int sfd = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in addr = {0};
    addr.sin_family = AF_INET; addr.sin_port = htons(port);
    inet_pton(AF_INET, host, &addr.sin_addr);
    if (connect(sfd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("connect"); goto cleanup;
    }

    SSL *ssl = SSL_new(ctx);
    SSL_set_fd(ssl, sfd);
    SSL_set_tlsext_host_name(ssl, "localhost");   /* SNI */
    if (SSL_connect(ssl) <= 0) {
        fprintf(stderr, "握手失败\n"); ERR_print_errors_fp(stderr);
        SSL_free(ssl); close(sfd); goto cleanup;
    }
    printf("握手完成, 协议=%s 套件=%s\n",
           SSL_get_version(ssl), SSL_get_cipher_name(ssl));

    const char *req = "GET / HTTP/1.1\r\nHost: localhost\r\n\r\n";
    SSL_write(ssl, req, strlen(req));
    char buf[512];
    int n = SSL_read(ssl, buf, sizeof(buf) - 1);
    if (n > 0) { buf[n] = '\0'; printf("响应:\n%s\n", buf); }

    SSL_shutdown(ssl);
    SSL_free(ssl);
    close(sfd);

cleanup:
    SSL_CTX_free(ctx);
    EVP_cleanup();
    return 0;
}
