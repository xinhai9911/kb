/*
 * hmac_hkdf.c — HMAC-SHA256 与 HKDF 密钥派生示例
 *
 * 演示（见 [[entities/OpenSSL_BoringSSL 开发集成实战]] §2、[[concepts/哈希函数与消息认证 HMAC]]）：
 *   - HMAC 作为带密钥的 MAC（注意用 CRYPTO_memcmp 比对，见 [[concepts/侧信道攻击与常量时间实现]]）
 *   - HKDF 从共享秘密派生出「客户端写密钥 / 服务端写密钥」两把独立密钥
 *
 * 编译：见 ../scripts/build.sh
 */
#include <stdio.h>
#include <string.h>
#include <openssl/hmac.h>
#include <openssl/kdf.h>
#include <openssl/evp.h>

static void hexprint(const char *label, const unsigned char *b, int n)
{
    printf("%s: ", label);
    for (int i = 0; i < n; i++) printf("%02x", b[i]);
    printf("\n");
}

/* HKDF-Expand: 从 secret 派生出 len 字节，info 区分不同用途 */
static int hkdf_expand(const unsigned char *secret, size_t secretlen,
                       const unsigned char *info, size_t infolen,
                       unsigned char *out, size_t outlen)
{
    EVP_PKEY_CTX *pctx = EVP_PKEY_CTX_new_id(EVP_PKEY_HKDF, NULL);
    if (!pctx) return -1;
    if (EVP_PKEY_derive_init(pctx) <= 0
        || EVP_PKEY_CTX_set_hkdf_md(pctx, EVP_sha256()) <= 0
        || EVP_PKEY_CTX_set1_hkdf_key(pctx, secret, secretlen) <= 0
        || EVP_PKEY_CTX_set1_hkdf_info(pctx, info, infolen) <= 0
        || EVP_PKEY_derive(pctx, out, &outlen) <= 0) {
        EVP_PKEY_CTX_free(pctx);
        return -1;
    }
    EVP_PKEY_CTX_free(pctx);
    return 0;
}

int main(void)
{
    /* 1) HMAC 示例 */
    unsigned char key[] = "shared-secret-key";
    unsigned char msg[] = "authenticated message";
    unsigned char mac[32];
    unsigned int maclen;

    HMAC(EVP_sha256(), key, sizeof(key) - 1, msg, sizeof(msg) - 1, mac, &maclen);
    hexprint("HMAC-SHA256", mac, maclen);

    /* 2) HKDF 示例：模拟 TLS 从 ECDHE 共享秘密派生两把方向密钥 */
    unsigned char shared_secret[32];
    for (int i = 0; i < 32; i++) shared_secret[i] = (unsigned char) i;  /* 占位 */

    unsigned char client_key[32], server_key[32];
    if (hkdf_expand(shared_secret, sizeof(shared_secret),
                    (unsigned char *)"tls13 client key", 17, client_key, 32) != 0
        || hkdf_expand(shared_secret, sizeof(shared_secret),
                       (unsigned char *)"tls13 server key", 17, server_key, 32) != 0) {
        fprintf(stderr, "HKDF failed\n");
        return 1;
    }
    hexprint("client_key", client_key, 32);
    hexprint("server_key", server_key, 32);

    /* info 不同 → 派生结果应不同 */
    int diff = CRYPTO_memcmp(client_key, server_key, 32) != 0;
    printf("client/server keys differ (expected 1): %d\n", diff);

    return 0;
}
