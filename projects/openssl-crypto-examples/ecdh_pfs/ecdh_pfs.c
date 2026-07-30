/*
 * ecdh_pfs.c — ECDHE (X25519) 密钥协商演示前向保密 (PFS)
 *
 * 演示（见 [[concepts/非对称加密与密钥交换 RSA_ECC_ECDHE]] §4、[[concepts/TLS 协议握手与记录层]] §6）：
 *   - 双方各自生成临时密钥对
 *   - 交换公钥 → 各自算出相同共享秘密（窃听者无法算出）
 *   - 每次连接换新密钥对 → 前向保密：长期私钥泄露也不影响历史会话
 *
 * 编译：见 ../scripts/build.sh
 */
#include <stdio.h>
#include <string.h>
#include <openssl/evp.h>
#include <openssl/core_names.h>

static void hexprint(const char *label, const unsigned char *b, int n)
{
    printf("%s: ", label);
    for (int i = 0; i < n; i++) printf("%02x", b[i]);
    printf("\n");
}

/* 用 X25519 做一次 ECDHE，返回共享秘密；pubkey 输出本方公钥 */
static int ecdhe_derive(unsigned char *shared, size_t *sharedlen,
                        unsigned char *pubkey, size_t *pubkeylen)
{
    EVP_PKEY *pkey = NULL;
    EVP_PKEY_CTX *kctx = NULL, *dctx = NULL;
    unsigned char peer_pub[32];   /* 对端公钥（实际中通过网络收到） */
    size_t len;

    /* 生成 X25519 临时密钥对 */
    kctx = EVP_PKEY_CTX_new_id(EVP_PKEY_X25519, NULL);
    if (!kctx || EVP_PKEY_keygen_init(kctx) <= 0
        || EVP_PKEY_keygen(kctx, &pkey) <= 0) goto fail;

    /* 导出本方公钥 */
    len = *pubkeylen;
    if (EVP_PKEY_get_raw_public_key(pkey, pubkey, &len) <= 0) goto fail;
    *pubkeylen = len;

    /* 为演示：自己生成“对端”密钥对，取其公钥作为 peer_pub */
    EVP_PKEY *peer = NULL;
    EVP_PKEY_CTX *kctx2 = EVP_PKEY_CTX_new_id(EVP_PKEY_X25519, NULL);
    if (!kctx2 || EVP_PKEY_keygen_init(kctx2) <= 0
        || EVP_PKEY_keygen(kctx2, &peer) <= 0) { EVP_PKEY_CTX_free(kctx2); goto fail; }
    EVP_PKEY_CTX_free(kctx2);
    len = sizeof(peer_pub);
    if (EVP_PKEY_get_raw_public_key(peer, peer_pub, &len) <= 0) { EVP_PKEY_free(peer); goto fail; }

    /* 用本方私钥 + 对端公钥派生共享秘密 */
    dctx = EVP_PKEY_CTX_new(pkey, NULL);
    if (!dctx || EVP_PKEY_derive_init(dctx) <= 0
        || EVP_PKEY_derive_set_peer(dctx, peer) <= 0) { EVP_PKEY_free(peer); goto fail; }

    len = *sharedlen;
    if (EVP_PKEY_derive(dctx, shared, &len) <= 0) { EVP_PKEY_free(peer); goto fail; }
    *sharedlen = len;

    EVP_PKEY_free(peer);
    EVP_PKEY_CTX_free(kctx);
    EVP_PKEY_CTX_free(dctx);
    EVP_PKEY_free(pkey);
    return 0;

fail:
    if (kctx) EVP_PKEY_CTX_free(kctx);
    if (dctx) EVP_PKEY_CTX_free(dctx);
    if (pkey) EVP_PKEY_free(pkey);
    return -1;
}

int main(void)
{
    unsigned char shared[32], pub[32];
    size_t sharedlen = sizeof(shared), publen = sizeof(pub);

    if (ecdhe_derive(shared, &sharedlen, pub, &publen) != 0) {
        fprintf(stderr, "ECDHE derive failed\n");
        return 1;
    }
    hexprint("my public key", pub, (int)publen);
    hexprint("shared secret", shared, (int)sharedlen);
    printf("shared secret length: %zu (X25519 → 32 bytes)\n", sharedlen);
    printf("PFS: 每次连接应重新调用 ecdhe_derive 生成新临时密钥对\n");
    return 0;
}
