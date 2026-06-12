from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse

from mail.models import MessageMeta, Mailbox

@staff_member_required
def email_list(request):
    qs = MessageMeta.objects.select_related('mailbox').order_by('-date')
    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_panel/email_list.html', {'page': page})

@staff_member_required
def email_detail(request, pk):
    email = get_object_or_404(MessageMeta, pk=pk)
    if request.method == 'POST':
        # Simple edit: allow changing folder or marking read/unread
        folder = request.POST.get('folder')
        seen = request.POST.get('seen')
        if folder:
            email.folder = folder
        if seen is not None:
            email.seen = seen == 'true'
        email.save()
        return redirect(reverse('admin_panel:email_detail', args=[pk]))
    return render(request, 'admin_panel/email_detail.html', {'email': email})

@staff_member_required
def email_delete(request, pk):
    email = get_object_or_404(MessageMeta, pk=pk)
    email.delete()
    return redirect('admin_panel:email_list')
