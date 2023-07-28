"""Mailer for emencia.django.newsletter"""
import mimetypes

from smtplib import SMTP
from smtplib import SMTPRecipientsRefused
from datetime import datetime

from email.utils import formatdate
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.encoders import encode_base64
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage

from sekizai.context import SekizaiContext
from html2text import html2text
from django.conf import settings
from django.contrib.sites.models import Site
from django.template import Context, Template
from django.template.loader import render_to_string
from django.utils.encoding import smart_str
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser

from emencia.django.newsletter.models import Newsletter
from emencia.django.newsletter.models import ContactMailingStatus
from emencia.django.newsletter.utils.tokens import tokenize
from emencia.django.newsletter.utils.newsletter import track_links
from emencia.django.newsletter.utils.newsletter import body_insertion
from emencia.django.newsletter.settings import (SEND_PLAINTEXT,
                                                TRACKING_LINKS,
                                                TRACKING_IMAGE,
                                                INCLUDE_UNSUBSCRIPTION,
                                                HTML_TEMPLATE,
                                                TEXT_TEMPLATE,
                                                MEDIA_URL as NEWSLETTER_MEDIA_URL)


class Mailer(object):
    """Mailer for generating and sending newsletters
    In test mode the mailer always send mails but do not log it"""
    smtp = None

    def __init__(self, newsletter, test=False):
        self.test = test
        self.newsletter = newsletter
        self.expedition_list = self.get_expedition_list()
        self.newsletter_template = Template(self.newsletter.content)
        self.title_template = Template(self.newsletter.title)

    def run(self):
        """Send the mails"""
        if not self.can_send:
            return

        if not self.smtp:
            self.smtp_connect()

        self.attachments = self.build_attachments()


        for contact in self.expedition_list:
            message = self.build_message(contact)
            try:
                self.smtp.sendmail(self.newsletter.header_sender,
                                   contact.email,
                                   message.as_string())
                status = self.test and ContactMailingStatus.SENT_TEST \
                         or ContactMailingStatus.SENT
            except SMTPRecipientsRefused as e:
                status = ContactMailingStatus.INVALID
                contact.valid = False
                contact.save()
            except:
                status = ContactMailingStatus.ERROR

            ContactMailingStatus.objects.create(newsletter=self.newsletter,
                                                contact=contact, status=status)
        self.smtp.quit()
        self.update_newsletter_status()

    def build_message(self, contact):
        """
        Build the email as a multipart message containing
        a multipart alternative for text (plain, HTML) plus
        all the attached files.
        """
        if not SEND_PLAINTEXT:
            content_html = self.build_email_content(contact, HTML_TEMPLATE, plain=False)
            if TEXT_TEMPLATE:
                content_text = self.build_email_content(contact, TEXT_TEMPLATE, plain=True)
            else:
                content_text = html2text(content_html)
        else:
            content_text = self.build_email_content(contact, TEXT_TEMPLATE, plain=True)

        message = MIMEMultipart()

        message['Subject'] = self.build_title_content(contact)
        message['From'] = self.newsletter.header_sender
        message['Reply-to'] = self.newsletter.header_reply
        message['To'] = contact.mail_format()
        message['Date'] = formatdate()

        message_alt = MIMEMultipart('alternative')

        message_alt.attach(MIMEText(smart_str(content_text), 'plain', 'UTF-8'))
        if not SEND_PLAINTEXT:
            message_alt.attach(MIMEText(smart_str(content_html), 'html', 'UTF-8'))

        message.attach(message_alt)

        for attachment in self.attachments:
            message.attach(attachment)

        for header, value in list(self.newsletter.server.custom_headers.items()):
            message[header] = value

        return message

    def build_attachments(self):
        """Build email's attachment messages"""
        attachments = []

        for attachment in self.newsletter.attachment_set.all():
            ctype, encoding = mimetypes.guess_type(attachment.file_attachment.path)

            if ctype is None or encoding is not None:
                ctype = 'application/octet-stream'

            maintype, subtype = ctype.split('/', 1)

            fd = open(attachment.file_attachment.path, 'rb')
            if maintype == 'text':
                message_attachment = MIMEText(fd.read(), _subtype=subtype)
            elif maintype == 'message':
                message_attachment = email.message_from_file(fd)
            elif maintype == 'image':
                message_attachment = MIMEImage(fd.read(), _subtype=subtype)
            elif maintype == 'audio':
                message_attachment = MIMEAudio(fd.read(), _subtype=subtype)
            else:
                message_attachment = MIMEBase(maintype, subtype)
                message_attachment.set_payload(fd.read())
                encode_base64(message_attachment)
            fd.close()
            message_attachment.add_header('Content-Disposition', 'attachment',
                                          filename=attachment.title)
            attachments.append(message_attachment)

        return attachments

    def smtp_connect(self):
        """Make a connection to the SMTP"""
        self.smtp = self.newsletter.server.connect()

    def get_expedition_list(self):
        """Build the expedition list"""
        credits = self.newsletter.server.credits()
        if self.test:
            return self.newsletter.test_contacts.all()[:credits]

        already_sent = ContactMailingStatus.objects.filter(status=ContactMailingStatus.SENT,
                                                           newsletter=self.newsletter).values_list('contact__id', flat=True)
        expedition_list = self.newsletter.mailing_list.expedition_set().exclude(id__in=already_sent)
        return expedition_list[:credits]

    def build_title_content(self, contact):
        """Generate the email title for a contact"""
        context = Context({'contact': contact})
        title = self.title_template.render(context)
        return title

    def build_email_content(self, contact, template=None, plain=False):
        """Generate the mail for a contact"""
        uidb36, token = tokenize(contact)
        domain = Site.objects.get_current().domain



        class FakeRequest(object):
            REQUEST = {
                'language' : 'de'
            }
            GET = {}
            session = {}
            user = AnonymousUser()
            current_page = None

        request = FakeRequest()
        try:
            from cms.plugin_rendering import ContentRenderer
            content_renderer = ContentRenderer(request=request)
        except ImportError:
            content_renderer = None

        NEWSLETTER_PORTAL_URL = getattr(settings, "NEWSLETTER_PORTAL_URL", settings.PORTAL_URL)

        context = {
            'contact': contact,
            'domain': domain,
            'request' : request,
            'cms_content_renderer' : content_renderer,
            'newsletter': self.newsletter,
            'object': self.newsletter,
            'uidb36': uidb36, 'token': token,
            'PORTAL_URL' : settings.PORTAL_URL,
            'NEWSLETTER_PORTAL_URL' : NEWSLETTER_PORTAL_URL,
            'MEDIA_URL' : "http://" + domain + settings.MEDIA_URL,
            'NEWSLETTER_MEDIA_URL' : NEWSLETTER_MEDIA_URL,
        }

        context.update(getattr(settings, "NEWSLETTER_ADDITIONAL_CONTEXT", {}))

        content = self.newsletter_template.render(SekizaiContext(context))

        if template:
            context.update({'content':content})
            try:
                content = render_to_string(template, context.flatten())
            except AttributeError:
                content = render_to_string(template, context)

        try:
            flat_context = context.flatten()
        except AttributeError:
            flat_context = context

        if not plain and TRACKING_LINKS:
            content = track_links(content, context)


        if not plain and INCLUDE_UNSUBSCRIPTION:
            unsubscription = render_to_string('newsletter/newsletter_link_unsubscribe.html', flat_context)
            content = body_insertion(content, unsubscription, end=True)

        if not plain and TRACKING_IMAGE:
           image_tracking = render_to_string('newsletter/newsletter_image_tracking.html', flat_context)
           content = body_insertion(content, image_tracking, end=True)


        return content


    def update_newsletter_status(self):
        """Update the status of the newsletter"""
        if self.test:
            return

        if self.newsletter.status == Newsletter.WAITING:
            self.newsletter.status = Newsletter.SENDING
        if self.newsletter.status == Newsletter.SENDING and \
               self.newsletter.mails_sent() >= \
               self.newsletter.mailing_list.expedition_set().count():
            self.newsletter.status = Newsletter.SENT
        self.newsletter.save()

    @property
    def can_send(self):
        """Check if the newsletter can be sent"""
        if self.newsletter.server.credits() <= 0:
            return False

        if self.test:
            return True

        if self.newsletter.sending_date <= timezone.now() and \
               (self.newsletter.status == Newsletter.WAITING or \
                self.newsletter.status == Newsletter.SENDING):
            return True

        return False

