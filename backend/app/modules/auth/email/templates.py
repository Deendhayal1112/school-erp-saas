"""
Dependency-free HTML and Text Email Templates with Brand Customization.
"""

# Standard brand styling parameters
BRAND_NAME = "School ERP SaaS"
BRAND_PRIMARY_COLOR = "#2563eb"  # Modern blue
BRAND_BACKGROUND_COLOR = "#f3f4f6"

# Helper CSS layout for HTML emails
HTML_BASE_WRAPPER = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: {{ bg_color }};
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 600px;
            background-color: #ffffff;
            margin: 0 auto;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        }
        .header {
            background-color: {{ primary_color }};
            color: #ffffff;
            text-align: center;
            padding: 30px 20px;
        }
        .header h1 {
            margin: 0;
            font-size: 24px;
            font-weight: 700;
        }
        .content {
            padding: 30px 20px;
            color: #374151;
            line-height: 1.6;
        }
        .button-container {
            text-align: center;
            margin: 30px 0;
        }
        .button {
            background-color: {{ primary_color }};
            color: #ffffff !important;
            text-decoration: none;
            padding: 12px 24px;
            border-radius: 6px;
            font-weight: 600;
            display: inline-block;
        }
        .footer {
            background-color: #f9fafb;
            text-align: center;
            padding: 20px;
            font-size: 12px;
            color: #6b7280;
            border-top: 1px solid #f3f4f6;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ brand_name }}</h1>
        </div>
        <div class="content">
            {{ body_html }}
        </div>
        <div class="footer">
            <p>&copy; 2026 {{ brand_name }}. All rights reserved.</p>
            <p>This is an automated security notification. Please do not reply directly.</p>
        </div>
    </div>
</body>
</html>
"""

# ===========================================================================
# 1. Verification Email Template
# ===========================================================================
VERIFICATION_HTML = """
<h2>Activate Your Account</h2>
<p>Hello {{ name }},</p>
<p>Thank you for registering. Please click the button below to verify your email address and activate your account:</p>
<div class="button-container">
    <a href="{{ action_url }}" class="button">Verify Email Address</a>
</div>
<p>If the button doesn't work, you can copy and paste the following link into your browser:</p>
<p><a href="{{ action_url }}">{{ action_url }}</a></p>
<p>This link will expire in {{ expire_mins }} minutes.</p>
"""

VERIFICATION_TEXT = """
Activate Your Account

Hello {{ name }},

Thank you for registering. Please click the link below to verify your email address and activate your account:

{{ action_url }}

This link will expire in {{ expire_mins }} minutes.

--
© 2026 {{ brand_name }}. All rights reserved.
"""

# ===========================================================================
# 2. Password Reset Email Template
# ===========================================================================
PASSWORD_RESET_HTML = """
<h2>Reset Your Password</h2>
<p>Hello {{ name }},</p>
<p>We received a request to reset the password associated with your account. Click the button below to choose a new password:</p>
<div class="button-container">
    <a href="{{ action_url }}" class="button">Reset Password</a>
</div>
<p>If the button doesn't work, copy and paste the following link into your browser:</p>
<p><a href="{{ action_url }}">{{ action_url }}</a></p>
<p>This link will expire in {{ expire_mins }} minutes.</p>
<p>If you did not request this, you can safely ignore this email.</p>
"""

PASSWORD_RESET_TEXT = """
Reset Your Password

Hello {{ name }},

We received a request to reset the password associated with your account. Please click the link below to choose a new password:

{{ action_url }}

This link will expire in {{ expire_mins }} minutes.

If you did not request this, you can safely ignore this email.

--
© 2026 {{ brand_name }}. All rights reserved.
"""

# ===========================================================================
# 3. Welcome Email Template
# ===========================================================================
WELCOME_HTML = """
<h2>Welcome to {{ brand_name }}!</h2>
<p>Hello {{ name }},</p>
<p>Your email has been verified, and your account is now fully active.</p>
<p>You can now log in to the portal and configure your organization settings.</p>
<div class="button-container">
    <a href="{{ action_url }}" class="button">Log In to Portal</a>
</div>
"""

WELCOME_TEXT = """
Welcome to {{ brand_name }}!

Hello {{ name }},

Your email has been verified, and your account is now fully active.

You can now log in to the portal at:
{{ action_url }}

--
© 2026 {{ brand_name }}. All rights reserved.
"""

# ===========================================================================
# 4. Account Activated Email Template
# ===========================================================================
ACTIVATED_HTML = """
<h2>Account Activated</h2>
<p>Hello {{ name }},</p>
<p>Your administrator account has been successfully verified and activated.</p>
<p>If you did not trigger this activation, please contact support immediately.</p>
"""


# ===========================================================================
# Render Engines
# ===========================================================================
def _simple_render(template_str: str, context: dict) -> str:
    """
    Dependency-free parser substituting jinja-style variables (e.g. {{ key }}) with values.
    """
    rendered = template_str
    for key, val in context.items():
        # Handle formats with potential spaces like {{ key }} or {{key}}
        rendered = rendered.replace(f"{{{{ {key} }}}}", str(val))
        rendered = rendered.replace(f"{{{{{key}}}}}", str(val))
    return rendered


def render_template(
    html_body_tmpl: str, text_body_tmpl: str, context: dict
) -> tuple[str, str]:
    """
    Renders HTML wrapper and plaintext templates with brand styles and specific contexts.
    """
    full_context = {
        "brand_name": BRAND_NAME,
        "primary_color": BRAND_PRIMARY_COLOR,
        "bg_color": BRAND_BACKGROUND_COLOR,
        **context,
    }

    # Render text body
    text_rendered = _simple_render(text_body_tmpl, full_context)

    # Render HTML body, then inject it into base layout wrapper
    body_html_rendered = _simple_render(html_body_tmpl, full_context)
    html_rendered = _simple_render(
        HTML_BASE_WRAPPER.replace("{{ body_html }}", body_html_rendered), full_context
    )

    return html_rendered, text_rendered
