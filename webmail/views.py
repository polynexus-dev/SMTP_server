from django.conf import settings
from django.contrib import messages as flash
from django.contrib.auth.decorators import login_required
from django.contrib.postgres.search import SearchQuery
from django.core.paginator import Paginator
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from mail.imap import ImapUnavailable, open_mailbox
from mail.models import MessageMeta
from mail.smtp import build_message, send

from django.db.models import Max
from django.utils import timezone
from email.utils import parsedate_to_datetime

def _mailbox_or_404(request):
    mb = request.user.mailboxes.filter(active=True).first()
    if mb is None:
        from accounts.models import Mailbox
        # Fallback 1: If username contains '@', look up mailbox by exact address
        if "@" in request.user.username:
            local, dom = request.user.username.rsplit("@", 1)
            mb = Mailbox.objects.filter(local_part=local.lower().strip(), domain__name=dom.lower().strip(), active=True).first()
        
        # Fallback 1.5: If user's email field contains '@', look up mailbox by exact address
        if mb is None and getattr(request.user, "email", None) and "@" in request.user.email:
            local, dom = request.user.email.rsplit("@", 1)
            mb = Mailbox.objects.filter(local_part=local.lower().strip(), domain__name=dom.lower().strip(), active=True).first()
        
        # Fallback 2: Look up mailbox where local_part matches the username (e.g. 'admin' matches 'admin@polynexus.in')
        if mb is None:
            mb = Mailbox.objects.filter(local_part=request.user.username.lower().strip(), active=True).first()
            
    if mb is None:
        if request.user.is_staff:
            return None
        raise Http404("No mailbox is attached to this account.")
    return mb


@login_required
def inbox(request, folder: str = "INBOX"):
    mb = _mailbox_or_404(request)
    if mb is None:
        return redirect("admin_panel:email_list")

    # Sync new mail from Dovecot on inbox load / refresh
    from mail.tasks import index_mailbox
    try:
        index_mailbox.run(None, mb.id, folder)
    except Exception:
        pass

    qs = MessageMeta.objects.filter(mailbox=mb, folder=folder)
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    return render(request, "webmail/inbox.html",
                  {"mailbox": mb, "folder": folder, "page": page})


@login_required
def message_detail(request, folder: str, uid: int):
    mb = _mailbox_or_404(request)
    if mb is None:
        return redirect("admin_panel:email_list")
    try:
        with open_mailbox(mb.address, folder) as imap:
            msg = next(iter(imap.fetch(f"UID {uid}", mark_seen=True)), None)
    except ImapUnavailable:
        flash.error(request, "Mail server is unreachable right now.")
        return redirect("inbox")
    if msg is None or int(msg.uid) != uid:
        raise Http404
    MessageMeta.objects.filter(mailbox=mb, folder=folder, uid=uid).update(seen=True)
    return render(request, "webmail/message.html", {
        "mailbox": mb, "folder": folder, "msg": msg,
        # Render plain text only; HTML bodies must be sanitized (e.g. bleach/nh3)
        # and served with a strict CSP before you ever mark them safe.
        "body": msg.text or "(no plain-text part; HTML rendering not enabled)",
    })


@login_required
@require_POST
def message_delete(request, folder: str, uid: int):
    mb = _mailbox_or_404(request)
    if mb is None:
        return redirect("admin_panel:email_list")
    with open_mailbox(mb.address, folder) as imap:
        imap.delete([str(uid)])
    MessageMeta.objects.filter(mailbox=mb, folder=folder, uid=uid).delete()
    flash.success(request, "Message deleted.")
    return redirect("inbox")


@login_required
def compose(request):
    mb = _mailbox_or_404(request)
    if mb is None:
        flash.info(request, "Please create a mailbox first to send emails.")
        return redirect("admin_panel:mailbox_list")
    if request.method == "POST":
        to = [a.strip() for a in request.POST.get("to", "").split(",") if a.strip()]
        if not to:
            return HttpResponseBadRequest("Recipient required")
        attachments = []
        for f in request.FILES.getlist("attachments"):
            if f.size > settings.MAX_ATTACHMENT_BYTES:
                flash.error(request, f"{f.name} exceeds the attachment size limit.")
                return redirect("compose")
            attachments.append((f.name, f.read(), f.content_type or "application/octet-stream"))
        msg = build_message(
            from_addr=mb.address, to=to,
            subject=request.POST.get("subject", ""),
            body=request.POST.get("body", ""),
            attachments=attachments,
        )
        
        smtp_failed = False
        try:
            send(msg)
        except Exception:
            smtp_failed = True
        
        # Save a copy to the Sent folder on the IMAP server and trigger index
        try:
            with open_mailbox(mb.address, "INBOX") as imap:
                if not imap.folder.exists("Sent"):
                    imap.folder.create("Sent")
            with open_mailbox(mb.address, "Sent") as imap:
                imap.append(msg.as_bytes(), "Sent")
            
            # Sync the Sent folder immediately in the database
            from mail.tasks import index_mailbox
            index_mailbox.run(None, mb.id, "Sent")
        except Exception:
            # Fallback: create database record directly if mail server is offline/unavailable
            # so the "Sent" section shows the email locally.
            try:
             
                
                last_uid = MessageMeta.objects.filter(mailbox=mb, folder="Sent").aggregate(Max("uid"))["uid__max"] or 0
                
                date_val = timezone.now()
                if msg.get("Date"):
                    try:
                        date_val = parsedate_to_datetime(msg.get("Date"))
                    except Exception:
                        pass
                
                has_attachments = bool(attachments)
                
                MessageMeta.objects.create(
                    mailbox=mb,
                    folder="Sent",
                    uid=last_uid + 1,
                    message_id=msg.get("Message-ID", "")[:998],
                    subject=msg.get("Subject", ""),
                    from_addr=mb.address,
                    to_addrs=", ".join(to),
                    date=date_val,
                    size=len(msg.as_bytes()),
                    seen=True,
                    flagged=False,
                    has_attachments=has_attachments,
                    snippet=request.POST.get("body", "")[:280],
                )
            except Exception:
                pass

        if smtp_failed:
            flash.warning(request, "Message saved to Sent locally (SMTP relay is currently offline).")
        else:
            flash.success(request, "Message sent.")
        return redirect("inbox")
    return render(request, "webmail/compose.html", {
        "mailbox": mb,
        "to": request.GET.get("to", ""),
        "subject": request.GET.get("subject", ""),
    })


@login_required
def search(request):
    mb = _mailbox_or_404(request)
    if mb is None:
        return redirect("admin_panel:email_list")
    q = request.GET.get("q", "").strip()
    results = MessageMeta.objects.none()
    if q:
        results = MessageMeta.objects.filter(
            mailbox=mb, search_vector=SearchQuery(q)
        )[:100]
    return render(request, "webmail/search.html", {"mailbox": mb, "q": q, "results": results})
