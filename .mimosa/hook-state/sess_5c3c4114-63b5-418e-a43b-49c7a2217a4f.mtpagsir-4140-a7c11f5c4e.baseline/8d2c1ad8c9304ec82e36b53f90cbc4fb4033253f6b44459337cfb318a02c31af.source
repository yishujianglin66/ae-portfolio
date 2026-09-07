"""密码哈希工具。

直接使用 `bcrypt`（而非已停止维护的 passlib）。bcrypt 5.x 的 `hashpw` /
`checkpw` API 稳定，避免了 passlib 1.7.4 与新版 bcrypt 不兼容的坑。

注意：bcrypt 只取密码前 72 字节；超过部分被忽略。生产环境若担心超长
密码，可在哈希前先做一次 SHA-256 摘要。
"""
import bcrypt


def hash_password(password: str) -> str:
    """对明文密码做单向哈希，返回可安全存储的摘要字符串。"""
    digest = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return digest.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与存储摘要是否匹配。"""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )
