"""Views for emencia.django.newsletter Newsletter"""
from django.template import RequestContext
from django.shortcuts import get_object_or_404
from django.shortcuts import render

from django.contrib.sites.models import Site
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string as render_file

from emencia.django.newsletter.models import Newsletter
from emencia.django.newsletter.models import ContactMailingStatus
from emencia.django.newsletter.utils import render_string
from emencia.django.newsletter.utils.newsletter import body_insertion
from emencia.django.newsletter.utils.newsletter import track_links
from emencia.django.newsletter.utils.tokens import untokenize
from emencia.django.newsletter.settings import (TRACKING_LINKS,
                                                HTML_TEMPLATE,
                                                TEXT_TEMPLATE,
                                                SEND_PLAINTEXT)


def render_newsletter(request, slug, context):
    """Return a newsletter in HTML format"""
    newsletter = get_object_or_404(Newsletter, slug=slug)
    context.update({'newsletter': newsletter,
                    'domain': Site.objects.get_current().domain})

    content = render_string(newsletter.content, context)
    title = render_string(newsletter.title, context)
    if TRACKING_LINKS:
        content = track_links(content, context)
    # unsubscription = render_file('newsletter/newsletter_link_unsubscribe.html', context)
    # content = body_insertion(content, unsubscription, end=True)

    template = 'newsletter/newsletter_detail.html'
    if HTML_TEMPLATE or TEXT_TEMPLATE:
        template = SEND_PLAINTEXT and TEXT_TEMPLATE or HTML_TEMPLATE

    context.update({'content': content,
                    'title': title,
                    'object': newsletter,
                    'PREVIEW' : True
                  })

    return render(request, template, context)


@login_required
def view_newsletter_preview(request, slug):
    """View of the newsletter preview"""
    context = {'contact': request.user,
               'preview' : True }
    return render_newsletter(request, slug, context)

def view_newsletter_contact(request, slug, uidb36, token):
    """Visualization of a newsletter by an user"""
    newsletter = get_object_or_404(Newsletter, slug=slug)
    contact = untokenize(uidb36, token)
    log = ContactMailingStatus.objects.create(newsletter=newsletter,
                                              contact=contact,
                                              status=ContactMailingStatus.OPENED_ON_SITE)
    context = {'contact': contact,
               'uidb36': uidb36, 'token': token}

    return render_newsletter(request, slug, context)

