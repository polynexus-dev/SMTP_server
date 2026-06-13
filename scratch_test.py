from mail.smtp import build_message

msg = build_message(
    from_addr="alice@example.com",
    to=["bob@example.org"],
    subject="Hello \u263a! This is a test of non-ASCII subject lines.",
    body="Hello world"
)
print("Subject header value:", msg.get("Subject"))
print("Subject header type:", type(msg.get("Subject")))
print("Subject header repr:", repr(msg.get("Subject")))
print("Subject header as string:", str(msg.get("Subject")))
