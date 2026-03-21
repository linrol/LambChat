"""HTML email template renderer with cross-client compatibility."""

from __future__ import annotations

import html
from typing import Optional


class EmailTemplate:
    """Email template renderer with consistent styling.

    All plain-text fields are HTML-escaped to prevent XSS.
    HTML fields (greeting, content, footer) are passed through as-is;
    callers must escape any user-provided values before inserting.
    """

    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters to prevent XSS attacks."""
        return html.escape(str(text), quote=True)

    @staticmethod
    def _escape_url(url: str) -> str:
        """Validate and escape URL to prevent javascript: and data: URL attacks."""
        url = str(url).strip()
        if url.startswith(("http://", "https://")):
            return html.escape(url, quote=True)
        return ""

    @staticmethod
    def render(
        title: str,
        icon_url: str,
        heading: str,
        greeting: str,
        content: str,
        button_url: str,
        button_text: str,
        footer: Optional[str] = None,
    ) -> str:
        """Render HTML email template with XSS protection.

        Args:
            title: Email title in header (plain text, will be escaped)
            icon_url: URL to the brand icon image
            heading: Main heading (plain text, will be escaped)
            greeting: Greeting HTML (may contain <strong>, <br>, etc.)
            content: Content HTML (may contain <br>, etc.)
            button_url: Button link URL (validated to only allow http/https)
            button_text: Button text (plain text, will be escaped)
            footer: Optional footer HTML (may contain <br>, etc.)

        Returns:
            Complete HTML email content.
        """
        safe_title = EmailTemplate._escape_html(title)
        safe_heading = EmailTemplate._escape_html(heading)
        safe_button_url = EmailTemplate._escape_url(button_url)
        safe_button_text = EmailTemplate._escape_html(button_text)
        safe_icon_url = EmailTemplate._escape_url(icon_url)

        icon_html = (
            f'<img src="{safe_icon_url}" alt="{safe_title}" width="48" height="48" '
            f'style="display: block; border: 0; width: 48px; height: 48px; margin: 0 auto;" class="mobile-full">'
            if safe_icon_url
            else ""
        )

        footer_html = (
            f'<tr><td style="padding: 0 40px 36px 40px; text-align: center;">'
            f'<p style="margin: 0; color: #78716c; font-size: 13px; line-height: 1.5;">{footer}</p>'
            f"</td></tr>"
            if footer
            else ""
        )

        if safe_button_url:
            button_html = (
                f'<!--[if mso]><v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" '
                f'xmlns:w="urn:schemas-microsoft-com:office:word" href="{safe_button_url}" '
                f'style="height:48px;v-text-anchor:middle;width:280px;" arcsize="20%" '
                f'strokecolor="#57534e" fillcolor="#57534e"><w:anchorlock/>'
                f'<center style="color:#ffffff;font-family:Helvetica,Arial,sans-serif;'
                f'font-size:15px;font-weight:bold;">{safe_button_text}</center></v:roundrect><![endif]-->'
                f'<table cellpadding="0" cellspacing="0" border="0" role="presentation" '
                f'align="center" style="margin: 0 auto;" class="mobile-button-container">'
                f'<tr><td align="center" style="border-radius: 8px; background-color: #57534e;" '
                f'class="mobile-button-bg">'
                f'<a href="{safe_button_url}" target="_blank" style="font-size: 15px; font-family: '
                f"Helvetica, Arial, sans-serif; font-weight: bold; color: #ffffff; text-decoration: none; "
                f"border-radius: 8px; padding: 14px 36px; border: 1px solid #57534e; display: inline-block; "
                f'mso-padding-alt: 0; text-align: center;">{safe_button_text}</a>'
                f"</td></tr></table>"
            )
        else:
            button_html = (
                f'<table cellpadding="0" cellspacing="0" border="0" role="presentation" '
                f'align="center" style="margin: 0 auto;">'
                f'<tr><td align="center" style="border-radius: 8px; background-color: #57534e;">'
                f'<span style="font-size: 15px; font-family: Helvetica, Arial, sans-serif; '
                f"font-weight: bold; color: #ffffff; border-radius: 8px; padding: 14px 36px; "
                f'display: inline-block; text-align: center;">{safe_button_text}</span>'
                f"</td></tr></table>"
            )

        preheader = EmailTemplate._escape_html(heading)

        return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <meta name="x-apple-disable-message-reformatting">
  <title>{safe_title} - {safe_heading}</title>
  <!--[if mso]>
  <noscript>
    <xml>
      <o:OfficeDocumentSettings>
        <o:AllowPNG/>
        <o:PixelsPerInch>96</o:PixelsPerInch>
      </o:OfficeDocumentSettings>
    </xml>
  </noscript>
  <![endif]-->
  <style type="text/css">
    body, table, td, a {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
    table, td {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
    img {{ -ms-interpolation-mode: bicubic; border: 0; height: auto; line-height: 100%; outline: none; text-decoration: none; }}
    body {{ margin: 0; padding: 0; width: 100% !important; height: 100% !important; }}
    .mobile-full {{ width: 100% !important; max-width: 100% !important; }}
    .mobile-padding {{ padding-left: 20px !important; padding-right: 20px !important; }}
    @media only screen and (max-width: 620px) {{
      .mobile-full {{ width: 100% !important; max-width: 100% !important; }}
      .mobile-padding {{ padding-left: 20px !important; padding-right: 20px !important; }}
      .mobile-stack {{ display: block !important; width: 100% !important; }}
      .mobile-text-center {{ text-align: center !important; }}
      .mobile-button-bg {{ width: 100% !important; text-align: center !important; }}
      .mobile-button-bg a {{ width: 100% !important; display: block !important; box-sizing: border-box !important; }}
    }}
  </style>
</head>
<body style="margin: 0; padding: 0; background-color: #f5f5f4; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1c1917; -webkit-font-smoothing: antialiased;">

  <!-- Preheader -->
  <div style="display: none; font-size: 1px; color: #f5f5f4; line-height: 1px; max-height: 0px; max-width: 0px; opacity: 0; overflow: hidden;">
    {preheader}&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;
  </div>

  <!-- Wrapper -->
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color: #f5f5f5;">
    <tr>
      <td align="center" style="padding: 32px 16px;">

        <!-- Main container 600px -->
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" class="mobile-full" style="max-width: 600px; width: 100%;">

          <!-- Header -->
          <tr>
            <td style="background-color: #78716c; border-radius: 12px 12px 0 0; padding: 40px 40px 32px 40px; text-align: center;" class="mobile-padding">
              <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                <tr>
                  <td style="padding-bottom: 16px;">
                    {icon_html}
                  </td>
                </tr>
                <tr>
                  <td>
                    <h1 style="margin: 0; padding: 0; font-size: 24px; font-weight: 700; line-height: 1.3; color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">{safe_title}</h1>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="background-color: #ffffff; padding: 40px; border-left: 1px solid #e7e5e4; border-right: 1px solid #e7e5e4;" class="mobile-padding">

              <!-- Heading -->
              <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                <tr>
                  <td style="padding-bottom: 24px;">
                    <h2 style="margin: 0; padding: 0; font-size: 20px; font-weight: 600; line-height: 1.4; color: #1c1917; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">{safe_heading}</h2>
                    <div style="margin-top: 16px; height: 3px; width: 48px; background-color: #78716c; border-radius: 2px;"></div>
                  </td>
                </tr>
              </table>

              <!-- Greeting -->
              <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                <tr>
                  <td style="padding-bottom: 20px; font-size: 15px; line-height: 1.7; color: #44403c;">
                    {greeting}
                  </td>
                </tr>
              </table>

              <!-- Content -->
              <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                <tr>
                  <td style="padding-bottom: 32px; font-size: 15px; line-height: 1.7; color: #44403c;">
                    {content}
                  </td>
                </tr>
              </table>

              <!-- CTA Button -->
              <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                <tr>
                  <td style="padding-bottom: 8px; text-align: center;">
                    {button_html}
                  </td>
                </tr>
              </table>

              <!-- Fallback link -->
              <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                <tr>
                  <td style="padding-bottom: 32px; text-align: center; font-size: 13px; line-height: 1.5; color: #78716c;">
                    {safe_button_url}
                  </td>
                </tr>
              </table>

              {footer_html}

            </td>
          </tr>

          <!-- Divider -->
          <tr>
            <td style="background-color: #ffffff; padding: 0 40px; border-left: 1px solid #e7e5e4; border-right: 1px solid #e7e5e4;" class="mobile-padding">
              <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                <tr>
                  <td style="border-top: 1px solid #e7e5e4; font-size: 1px; line-height: 1px;">&nbsp;</td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color: #ffffff; border-radius: 0 0 12px 12px; padding: 24px 40px 32px 40px; text-align: center; border-left: 1px solid #e7e5e4; border-right: 1px solid #e7e5e4; border-bottom: 1px solid #e7e5e4;" class="mobile-padding">
              <p style="margin: 0 0 8px 0; font-size: 13px; line-height: 1.5; color: #78716c;">
                {safe_title}
              </p>
              <p style="margin: 0; font-size: 12px; line-height: 1.5; color: #a8a29e;">
                This is an automated email. Please do not reply.
              </p>
            </td>
          </tr>

        </table>
        <!-- /Main container -->

      </td>
    </tr>
  </table>
  <!-- /Wrapper -->

</body>
</html>"""
