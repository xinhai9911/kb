/*
 * aes_gcm.c — AES-256-GCM 加解密示例（OpenSSL EVP 高层 API）
 *
 * 演示要点（见 [[entities/OpenSSL_BoringSSL 开发集成实战]] §1、[[concepts/对称加密 AES与ChaCha20]]）：
 *   - 用 EVP_CIPHER_CTX 做 AEAD
 *   - nonce(IV) 12 字节且每次必须唯一
 *   - AAD 参与认证但不加密
 *   - 解密时校验 GCM tag，不匹配则拒绝
 *
 * 编译：见 ../scripts/build.sh
 */
#include <stdio.h>
#include <string.h>
#include <openssl/evp.h>
#include <openssl/rand.h>

#define KEY_LEN   32   /* AES-256 */
#define IV_LEN    12   /* GCM 推荐 nonce 长度 */
#define TAG_LEN   16

/* 加密：输出 ct(与 plain 等长) + tag(16) + 使用传入 iv */
static int aes_gcm_encrypt(const unsigned char *key, const unsigned char *iv,
                           const unsigned char *aad, int aadlen,
                           const unsigned char *plain, int plainlen,
                           unsigned char *ct, int *ctlen,
                           unsigned char *tag)
{
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    int len, outlen = 0;
    if (!ctx) return -1;

    if (!EVP_EncryptInit_ex(ctx, EVP_aes_256_gcm(), NULL, NULL, NULL)
        || !EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_IVLEN, IV_LEN, (void *)iv)
        || !EVP_EncryptInit_ex(ctx, NULL, NULL, key, iv)) goto fail;

    if (aad && aadlen)
        if (!EVP_EncryptUpdate(ctx, NULL, &len, aad, aadlen)) goto fail;

    if (!EVP_EncryptUpdate(ctx, ct, &len, plain, plainlen)) goto fail;
    outlen = len;

    if (!EVP_EncryptFinal_ex(ctx, ct + len, &len)) goto fail;
    outlen += len;

    if (!EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_GET_TAG, TAG_LEN, tag)) goto fail;

    *ctlen = outlen;
    EVP_CIPHER_CTX_free(ctx);
    return 0;

fail:
    EVP_CIPHER_CTX_free(ctx);
    return -1;
}

/* 解密：校验 tag，成功则输出 plain，失败返回 -1 */
static int aes_gcm_decrypt(const unsigned char *key, const unsigned char *iv,
                           const unsigned char *aad, int aadlen,
                           const unsigned char *ct, int ctlen,
                           const unsigned char *tag,
                           unsigned char *plain, int *plainlen)
{
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    int len, outlen = 0;
    if (!ctx) return -1;

    if (!EVP_DecryptInit_ex(ctx, EVP_aes_256_gcm(), NULL, NULL, NULL)
        || !EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_IVLEN, IV_LEN, (void *)iv)
        || !EVP_DecryptInit_ex(ctx, NULL, NULL, key, iv)) goto fail;

    if (aad && aadlen)
        if (!EVP_DecryptUpdate(ctx, NULL, &len, aad, aadlen)) goto fail;

    if (!EVP_DecryptUpdate(ctx, plain, &len, ct, ctlen)) goto fail;
    outlen = len;

    /* 先设置期望 tag，再 Final 校验 */
    if (!EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_TAG, TAG_LEN, (void *)tag)) goto fail;

    if (!EVP_DecryptFinal_ex(ctx, plain + len, &len)) goto fail;  /* tag 不符返回 0 */
    outlen += len;

    *plainlen = outlen;
    EVP_CIPHER_CTX_free(ctx);
    return 0;

fail:
    EVP_CIPHER_CTX_free(ctx);
    return -1;
}

static void hexprint(const char *label, const unsigned char *b, int n)
{
    printf("%s: ", label);
    for (int i = 0; i < n; i++) printf("%02x", b[i]);
    printf("\n");
}

int main(void)
{
    unsigned char key[KEY_LEN], iv[IV_LEN], aad[] = "hdr-info", tag[TAG_LEN];
    unsigned char plain[] = "secret message from openssl example";
    unsigned char ct[sizeof(plain) + EVP_MAX_BLOCK_LENGTH];
    unsigned char dec[sizeof(plain)];
    int ctlen, declen;

    /* 生产环境用 RAND_bytes 生成 key/iv（见 [[concepts/侧信道攻击与常量时间实现]]） */
    if (RAND_bytes(key, KEY_LEN) != 1 || RAND_bytes(iv, IV_LEN) != 1) {
        fprintf(stderr, "RAND_bytes failed\n");
        return 1;
    }

    if (aes_gcm_encrypt(key, iv, aad, sizeof(aad) - 1, plain, sizeof(plain) - 1,
                        ct, &ctlen, tag) != 0) {
        fprintf(stderr, "encrypt failed\n");
        return 1;
    }

    hexprint("key", key, KEY_LEN);
    hexprint("iv ", iv, IV_LEN);
    hexprint("tag", tag, TAG_LEN);
    printf("ctlen=%d\n", ctlen);

    if (aes_gcm_decrypt(key, iv, aad, sizeof(aad) - 1, ct, ctlen, tag,
                        dec, &declen) != 0) {
        fprintf(stderr, "decrypt/tag verify failed\n");
        return 1;
    }
    dec[declen] = '\0';
    printf("decrypted: %s\n", dec);

    /* 演示 tamper 检测：篡改一个密文字节，tag 校验应失败 */
    ct[0] ^= 0x01;
    if (aes_gcm_decrypt(key, iv, aad, sizeof(aad) - 1, ct, ctlen, tag,
                        dec, &declen) == 0) {
        fprintf(stderr, "ERROR: tampered ciphertext passed verification!\n");
        return 1;
    }
    printf("tamper detected: verification correctly rejected\n");
    return 0;
}
