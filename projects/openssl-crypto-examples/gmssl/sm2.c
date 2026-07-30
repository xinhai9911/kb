/*
 * sm2.c — SM2 公钥示例（国密椭圆曲线，sm2p256v1）
 *
 * 演示（见 [[entities/国密 SM2_SM3_SM4 实战]] §4、[[concepts/非对称加密与密钥交换 RSA_ECC_ECDHE]]）：
 *   - 生成 SM2 密钥对（曲线 sm2p256v1，不同于 NIST P-256）
 *   - SM2 签名（用 SM3 做哈希，算法绑定）
 *   - SM2 验签
 *   - SM2 公钥加密 / 私钥解密
 *
 * 编译：需 GmSSL。见 ../scripts/build.sh（GMSL_PREFIX）
 */
#include <stdio.h>
#include <string.h>
#include <openssl/evp.h>
#include <openssl/ec.h>
#include <openssl/pem.h>

static void hexprint(const char *label, const unsigned char *b, int n)
{
    printf("%s: ", label);
    for (int i = 0; i < n; i++) printf("%02x", b[i]);
    printf("\n");
}

int main(void)
{
    int rc = 1;
    EVP_PKEY *pkey = NULL;
    EVP_PKEY_CTX *kctx = NULL, *sctx = NULL, *ectx = NULL;

    /* 1) 生成 SM2 密钥对 */
    kctx = EVP_PKEY_CTX_new_id(EVP_PKEY_SM2, NULL);
    if (!kctx || EVP_PKEY_keygen_init(kctx) <= 0
        || EVP_PKEY_keygen(kctx, &pkey) <= 0) {
        fprintf(stderr, "SM2 keygen failed\n");
        goto cleanup;
    }
    printf("SM2 密钥对生成成功 (曲线 sm2p256v1)\n");

    /* 2) SM2 签名（摘要用 SM3，EVP_PKEY_CTX_set_signature_md 设 SM3） */
    const unsigned char msg[] = "sm2 sign payload";
    unsigned char sig[256];
    size_t siglen = sizeof(sig);

    sctx = EVP_MD_CTX_new();
    if (!sctx || EVP_DigestSignInit(sctx, NULL, EVP_sm3(), NULL, pkey) <= 0
        || EVP_DigestSign(sctx, sig, &siglen, msg, sizeof(msg) - 1) <= 0) {
        fprintf(stderr, "SM2 sign failed\n");
        goto cleanup;
    }
    hexprint("SM2 signature", sig, (int)siglen);

    /* 3) SM2 验签 */
    EVP_MD_CTX *vctx = EVP_MD_CTX_new();
    int vok = (vctx && EVP_DigestVerifyInit(vctx, NULL, EVP_sm3(), NULL, pkey) > 0
               && EVP_DigestVerify(vctx, sig, siglen, msg, sizeof(msg) - 1) == 1);
    EVP_MD_CTX_free(vctx);
    printf("SM2 verify (expect 1): %d\n", vok);
    if (!vok) goto cleanup;

    /* 4) SM2 公钥加密 / 私钥解密 */
    const unsigned char plain[] = "sm2 encrypt me";
    unsigned char enc[256];
    size_t enclen = sizeof(enc);

    ectx = EVP_PKEY_CTX_new(pkey, NULL);
    if (!ectx || EVP_PKEY_encrypt_init(ectx) <= 0
        || EVP_PKEY_encrypt(ectx, enc, &enclen, plain, sizeof(plain) - 1) <= 0) {
        fprintf(stderr, "SM2 encrypt failed\n");
        goto cleanup;
    }
    hexprint("SM2 ciphertext", enc, (int)enclen);

    unsigned char dec[256];
    size_t declen = sizeof(dec);
    EVP_PKEY_CTX *dctx = EVP_PKEY_CTX_new(pkey, NULL);
    int dok = (dctx && EVP_PKEY_decrypt_init(dctx) > 0
               && EVP_PKEY_decrypt(dctx, dec, &declen, enc, enclen) > 0);
    EVP_PKEY_CTX_free(dctx);
    if (!dok) { fprintf(stderr, "SM2 decrypt failed\n"); goto cleanup; }
    dec[declen] = '\0';
    printf("SM2 decrypted: %s\n", dec);

    rc = 0;
cleanup:
    if (kctx) EVP_PKEY_CTX_free(kctx);
    if (sctx) EVP_MD_CTX_free(sctx);
    if (ectx) EVP_PKEY_CTX_free(ectx);
    if (pkey) EVP_PKEY_free(pkey);
    return rc;
}
