/*
 * sm3.c — SM3 哈希示例（国密，256-bit，类似 SHA-256）
 *
 * 演示（见 [[entities/国密 SM2_SM3_SM4 实战]] §2、[[concepts/哈希函数与消息认证 HMAC]]）：
 *   - 用 EVP 高层接口计算 SM3 摘要
 *   - 同时演示 HMAC-SM3（带密钥的 MAC）
 *
 * 编译：需 GmSSL（OpenSSL 国密分支）。见 ../scripts/build.sh（GMSL_PREFIX）
 */
#include <stdio.h>
#include <string.h>
#include <openssl/evp.h>
#include <openssl/hmac.h>

static void hexprint(const char *label, const unsigned char *b, int n)
{
    printf("%s: ", label);
    for (int i = 0; i < n; i++) printf("%02x", b[i]);
    printf("\n");
}

int main(void)
{
    const unsigned char msg[] = "sm3 hash example";
    unsigned char md[EVP_MAX_MD_SIZE];
    unsigned int mdlen;

    /* 1) SM3 摘要 */
    EVP_MD_CTX *ctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex(ctx, EVP_sm3(), NULL);
    EVP_DigestUpdate(ctx, msg, sizeof(msg) - 1);
    EVP_DigestFinal_ex(ctx, md, &mdlen);
    EVP_MD_CTX_free(ctx);
    hexprint("SM3", md, mdlen);   /* 应等同国密 SM3 标准值 */

    /* 2) HMAC-SM3（带密钥 MAC，见 [[concepts/哈希函数与消息认证 HMAC]] §3） */
    unsigned char key[] = "sm3-mac-key";
    unsigned char mac[EVP_MAX_MD_SIZE];
    unsigned int maclen;
    HMAC(EVP_sm3(), key, sizeof(key) - 1, msg, sizeof(msg) - 1, mac, &maclen);
    hexprint("HMAC-SM3", mac, maclen);

    return 0;
}
