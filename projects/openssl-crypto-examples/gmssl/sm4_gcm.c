/*
 * sm4_gcm.c — SM4-GCM 认证加密示例（国密 AEAD，类似 AES-256-GCM）
 *
 * 演示（见 [[entities/国密 SM2_SM3_SM4 实战]] §3、[[concepts/对称加密 AES与ChaCha20]]）：
 *   - SM4 是 128-bit 分组密码，GCM 模式提供 AEAD
 *   - 与 AES-GCM 调用方式一致，仅算法替换为 EVP_sm4_gcm()
 *   - nonce 12 字节且每次唯一；解密校验 tag
 *
 * 编译：需 GmSSL。见 ../scripts/build.sh（GMSL_PREFIX）
 */
#include <stdio.h>
#include <string.h>
#include <openssl/evp.h>
#include <openssl/rand.h>

#define IV_LEN   12
#define TAG_LEN  16

static void hexprint(const char *label, const unsigned char *b, int n)
{
    printf("%s: ", label);
    for (int i = 0; i < n; i++) printf("%02x", b[i]);
    printf("\n");
}

static int sm4_gcm_encrypt(const unsigned char *key, const unsigned char *iv,
                           const unsigned char *plain, int plainlen,
                           unsigned char *ct, int *ctlen, unsigned char *tag)
{
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    int len, out = 0;
    if (!ctx) return -1;
    if (!EVP_EncryptInit_ex(ctx, EVP_sm4_gcm(), NULL, NULL, NULL)
        || !EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_IVLEN, IV_LEN, (void *)iv)
        || !EVP_EncryptInit_ex(ctx, NULL, NULL, key, iv)) goto fail;
    if (!EVP_EncryptUpdate(ctx, ct, &len, plain, plainlen)) goto fail;
    out = len;
    if (!EVP_EncryptFinal_ex(ctx, ct + len, &len)) goto fail;
    out += len;
    if (!EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_GET_TAG, TAG_LEN, tag)) goto fail;
    *ctlen = out;
    EVP_CIPHER_CTX_free(ctx);
    return 0;
fail:
    EVP_CIPHER_CTX_free(ctx);
    return -1;
}

static int sm4_gcm_decrypt(const unsigned char *key, const unsigned char *iv,
                           const unsigned char *ct, int ctlen,
                           const unsigned char *tag,
                           unsigned char *plain, int *plainlen)
{
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    int len, out = 0;
    if (!ctx) return -1;
    if (!EVP_DecryptInit_ex(ctx, EVP_sm4_gcm(), NULL, NULL, NULL)
        || !EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_IVLEN, IV_LEN, (void *)iv)
        || !EVP_DecryptInit_ex(ctx, NULL, NULL, key, iv)) goto fail;
    if (!EVP_DecryptUpdate(ctx, plain, &len, ct, ctlen)) goto fail;
    out = len;
    if (!EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_TAG, TAG_LEN, (void *)tag)) goto fail;
    if (!EVP_DecryptFinal_ex(ctx, plain + len, &len)) goto fail;  /* tag 不符返回 0 */
    out += len;
    *plainlen = out;
    EVP_CIPHER_CTX_free(ctx);
    return 0;
fail:
    EVP_CIPHER_CTX_free(ctx);
    return -1;
}

int main(void)
{
    unsigned char key[16], iv[IV_LEN], tag[TAG_LEN];   /* SM4 密钥 128-bit */
    unsigned char plain[] = "国密 SM4-GCM 示例";
    unsigned char ct[sizeof(plain) + EVP_MAX_BLOCK_LENGTH];
    unsigned char dec[sizeof(plain)];
    int ctlen, declen;

    if (RAND_bytes(key, 16) != 1 || RAND_bytes(iv, IV_LEN) != 1) {
        fprintf(stderr, "RAND_bytes failed\n");
        return 1;
    }

    if (sm4_gcm_encrypt(key, iv, plain, sizeof(plain) - 1, ct, &ctlen, tag) != 0) {
        fprintf(stderr, "encrypt failed\n");
        return 1;
    }
    hexprint("key", key, 16);
    hexprint("tag", tag, TAG_LEN);
    printf("ctlen=%d\n", ctlen);

    if (sm4_gcm_decrypt(key, iv, ct, ctlen, tag, dec, &declen) != 0) {
        fprintf(stderr, "decrypt failed\n");
        return 1;
    }
    dec[declen] = '\0';
    printf("decrypted: %s\n", dec);
    return 0;
}
