from sucklesync.utils import debug

email_instance = None

class Email:
    def __init__(self, ss):
        from sucklesync import sucklesync
        self.ss = ss

        if not self.ss.mail["enabled"]:
            debugger.warning("email is disabled")
            return

        try:
            import pyzmail
        except Exception as e:
            self.ss.debugger.error("fatal exception: %s", (e,))
            self.ss.debugger.critical("failed to import pyzmail (as user %s), try: 'pip install pyzmail' or disable [Email], exiting.", (self.ss.debugger.whoami(),))

        if not len(self.ss.mail["to"]):
            self.ss.debugger.warning("no valid to address configured, email is disabled")
            self.ss.mail["enabled"] = False
            return

        if len(self.ss.mail["from"]) > 1:
            self.ss.debugger.warning("only able to send from one address, using %s", (self.ss.mail["from"][0],))
        elif not len(self.ss.mail["from"]):
            self.ss.debugger.warning("no valid from address configured, email is disabled")
            self.ss.mail["enabled"] = False
            return
        self.ss.mail["from"] = self.ss.mail["from"][0]

        if not self.ss.mail["mode"] in ["normal", "ssl", "tls"]:
            self.ss.debugger.warning("ignoring invalid email mode (%s), must be one of: normal, ssl, tls", (self.ss.mail["mode"],))
            self.ss.mail["mode"] = "normal"

    def MailSend(self, subject, body_text, body_html):
        try:
            import pyzmail
            payload, mail_from, rcpt_to, msg_id = pyzmail.generate.compose_mail(self.ss.mail["from"], self.ss.mail["to"], subject, "iso-8859-1", (body_text, "us-ascii"), (body_html, "us-ascii"))
            ret = pyzmail.generate.send_mail(payload, mail_from, rcpt_to, self.ss.mail["hostname"], self.ss.mail["port"], self.ss.mail["mode"], self.ss.mail["username"], self.ss.mail["password"])

            if isinstance(ret, dict):
                if ret:
                    failed_recipients = ", ".join(ret.keys())
                    self.ss.debugger.warning("failed to send email, failed receipients: %s", (failed_recipients,))
                else:
                    self.ss.debugger.debug("email sent: %s", (ret,))

        except Exception as e:
            self.ss.debugger.dump_exception("MailSend() exception")
