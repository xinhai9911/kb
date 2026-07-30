/*
 * tls_server.c — 最小 TLS 1.3 服务端（阻塞式，便于阅读）
 *
 * 演示（见 [[entities/OpenSSL_BoringSSL 开发集成实战]] §5、[[entities/Nginx TLS 配置与证书管理实战]]）：
 *   - SSL_CTX 配置：仅 TLS 1.3、AEAD 套件、ECDHE 曲线
 *   - 加载证书链与私钥（需提前用 openssl 生成，见 README）
 *   - SSL_accept 完成握手后读写应用数据（记录层 AEAD 自动处理）
 *
 * 编译：见 ../scripts/build.sh
 * 运行：先生成 cert（README），再 ./tls_server 4433
 * 测试：openssl s_client -connect 127.0.0.1:4433 -servername localhost
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <openssl/ssl.h>
#include <openssl/err.h>

#define CERT_FILE "server.crt"
#define KEY_FILE  "server.key"

int main(int argc, char **argv)
{
    int port = argc > 1 ? atoi(argv[1]) : 4433;

    SSL_load_error_strings();
    OpenSSL_add_ssl_algorithms();
    SSL_CTX *ctx = SSL_CTX_new(TLS_method());
    if (!ctx) { ERR_print_errors_fp(stderr); return 1; }

    /* 仅 TLS 1.3（见 [[concepts/TLS 协议握手与记录层]]） */
    SSL_CTX_set_min_proto_version(ctx, TLS1_3_VERSION);
    SSL_CTX_set_max_proto_version(ctx, TLS1_3_VERSION);

    /* 强制 AEAD 套件（见 [[concepts/对称加密 AES与ChaCha20]]） */
    if (SSL_CTX_set_ciphersuites(ctx,
        "TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:"
        "TLS_AES_128_GCM_SHA256") != 1) {
        ERR_print_errors_fp(stderr); goto cleanup;
    }
    /* 优先现代曲线（见 [[concepts/非对称加密与密钥交换 RSA_ECC_ECDHE]]） */
    SSL_CTX_set1_groups_list(ctx, "X25519:P-256");

    if (SSL_CTX_use_certificate_chain_file(ctx, CERT_FILE) != 1) {
        fprintf(stderr, "加载证书失败: %s\n", CERT_FILE);
        ERR_print_errors_fp(stderr); goto cleanup;
    }
    if (SSL_CTX_use_PrivateKey_file(ctx, KEY_FILE, SSL_FILETYPE_PEM) != 1) {
        fprintf(stderr, "加载私钥失败: %s\n", KEY_FILE);
        ERR_print_errors_fp(stderr); goto cleanup;
    }
    if (SSL_CTX_check_private_key(ctx) != 1) {
        fprintf(stderr, "证书与私钥不匹配\n"); goto cleanup;
    }

    /* TCP listen */
    int sfd = socket(AF_INET, SOCK_STREAM, 0);
    int opt = 1; setsockopt(sfd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    struct sockaddr_in addr = {0};
    addr.sin_family = AF_INET; addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(port);
    if (bind(sfd, (struct sockaddr *)&addr, sizeof(addr)) < 0
        || listen(sfd, 1) < 0) {
        perror("bind/listen"); goto cleanup;
    }
    printf("TLS 1.3 server listening on %d\n", port);

    int cfd = accept(sfd, NULL, NULL);
    SSL *ssl = SSL_new(ctx);
    SSL_set_fd(ssl, cfd);
    if (SSL_accept(ssl) <= 0) {
        fprintf(stderr, "握手失败\n"); ERR_print_errors_fp(stderr);
        SSL_free(ssl); close(cfd); goto cleanup;
    }
    printf("握手完成, 协议=%s 套件=%s\n",
           SSL_get_version(ssl), SSL_get_cipher_name(ssl));

    char buf[256];
    int n = SSL_read(ssl, buf, sizeof(buf) - 1);
    if (n > 0) {
        buf[n] = '\0';
        printf("收到: %s", buf);
        const char *resp = "HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nhi";
        SSL_write(ssl, resp, strlen(resp));
    }
    SSL_shutdown(ssl);
    SSL_free(ssl);
    close(cfd);

cleanup:
    close(sfd);
    SSL_CTX_free(ctx);
    EVP_cleanup();
    return 0;
}
