import ssl

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend as DjangoEmailBackend
from django.utils.functional import cached_property


class EmailBackend(DjangoEmailBackend):
    """
    SMTP backend that can optionally disable TLS certificate verification.

    This is needed in environments where the SMTP server presents a self-signed
    certificate (equivalent to verify_peer=0 / allow_self_signed=1).
    """

    @cached_property
    def ssl_context(self):
        if getattr(settings, "EMAIL_SSL_VERIFY", True):
            return super().ssl_context

        ctx = ssl._create_unverified_context()  # nosec - explicitly configured
        if self.ssl_certfile or self.ssl_keyfile:
            ctx.load_cert_chain(self.ssl_certfile, self.ssl_keyfile)
        return ctx

