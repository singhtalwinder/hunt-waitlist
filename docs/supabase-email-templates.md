# Hunt - Supabase Email Templates

These email templates are designed to match Hunt's brand style. Copy and paste each template into the corresponding section in your Supabase Dashboard under **Authentication > Email Templates**.

**Site URL Configuration:**
Before using these templates, make sure to set your Site URL in **Authentication > URL Configuration**:
- Production: `https://hunt.careers`
- Development: `http://localhost:3000`

---

## 1. Confirm Signup

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f9fafb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f9fafb;">
    <tr>
      <td align="center" style="padding: 40px 20px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 480px; background-color: #ffffff; border-radius: 12px; border: 1px solid #e5e7eb;">
          <!-- Header -->
          <tr>
            <td style="padding: 32px 32px 24px 32px; text-align: center; border-bottom: 1px solid #f3f4f6;">
              <img src="https://hunt.careers/paper.png" alt="Hunt" width="40" height="40" style="display: inline-block; vertical-align: middle;">
              <span style="display: inline-block; vertical-align: middle; margin-left: 8px; font-size: 24px; font-weight: 700; color: #000000;">hunt<span style="color: #FF4500;">.</span></span>
            </td>
          </tr>
          <!-- Content -->
          <tr>
            <td style="padding: 32px;">
              <h1 style="margin: 0 0 16px 0; font-size: 24px; font-weight: 600; color: #111827; text-align: center;">Confirm your email</h1>
              <p style="margin: 0 0 24px 0; font-size: 16px; line-height: 24px; color: #4b5563; text-align: center;">
                Click the button below to confirm your email and start using Hunt.
              </p>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td align="center">
                    <a href="{{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=email" style="display: inline-block; padding: 14px 32px; background-color: #FF4500; color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600; border-radius: 9999px;">Confirm Email</a>
                  </td>
                </tr>
              </table>
              <p style="margin: 24px 0 0 0; font-size: 14px; line-height: 20px; color: #9ca3af; text-align: center;">
                If you didn't create an account with Hunt, you can safely ignore this email.
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding: 24px 32px; border-top: 1px solid #f3f4f6; text-align: center;">
              <p style="margin: 0; font-size: 12px; color: #9ca3af;">
                Hunt - Find jobs you're actually likely to get.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
```

---

## 2. Reset Password

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f9fafb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f9fafb;">
    <tr>
      <td align="center" style="padding: 40px 20px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 480px; background-color: #ffffff; border-radius: 12px; border: 1px solid #e5e7eb;">
          <!-- Header -->
          <tr>
            <td style="padding: 32px 32px 24px 32px; text-align: center; border-bottom: 1px solid #f3f4f6;">
              <img src="https://hunt.careers/paper.png" alt="Hunt" width="40" height="40" style="display: inline-block; vertical-align: middle;">
              <span style="display: inline-block; vertical-align: middle; margin-left: 8px; font-size: 24px; font-weight: 700; color: #000000;">hunt<span style="color: #FF4500;">.</span></span>
            </td>
          </tr>
          <!-- Content -->
          <tr>
            <td style="padding: 32px;">
              <h1 style="margin: 0 0 16px 0; font-size: 24px; font-weight: 600; color: #111827; text-align: center;">Reset your password</h1>
              <p style="margin: 0 0 24px 0; font-size: 16px; line-height: 24px; color: #4b5563; text-align: center;">
                Click the button below to set a new password for your Hunt account.
              </p>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td align="center">
                    <a href="{{ .SiteURL }}/auth/callback?token_hash={{ .TokenHash }}&type=recovery&next=/reset-password" style="display: inline-block; padding: 14px 32px; background-color: #FF4500; color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600; border-radius: 9999px;">Reset Password</a>
                  </td>
                </tr>
              </table>
              <p style="margin: 24px 0 0 0; font-size: 14px; line-height: 20px; color: #9ca3af; text-align: center;">
                If you didn't request a password reset, you can safely ignore this email.
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding: 24px 32px; border-top: 1px solid #f3f4f6; text-align: center;">
              <p style="margin: 0; font-size: 12px; color: #9ca3af;">
                Hunt - Find jobs you're actually likely to get.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
```

---

## 3. Magic Link (if you enable passwordless login later)

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f9fafb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f9fafb;">
    <tr>
      <td align="center" style="padding: 40px 20px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 480px; background-color: #ffffff; border-radius: 12px; border: 1px solid #e5e7eb;">
          <!-- Header -->
          <tr>
            <td style="padding: 32px 32px 24px 32px; text-align: center; border-bottom: 1px solid #f3f4f6;">
              <img src="https://hunt.careers/paper.png" alt="Hunt" width="40" height="40" style="display: inline-block; vertical-align: middle;">
              <span style="display: inline-block; vertical-align: middle; margin-left: 8px; font-size: 24px; font-weight: 700; color: #000000;">hunt<span style="color: #FF4500;">.</span></span>
            </td>
          </tr>
          <!-- Content -->
          <tr>
            <td style="padding: 32px;">
              <h1 style="margin: 0 0 16px 0; font-size: 24px; font-weight: 600; color: #111827; text-align: center;">Sign in to Hunt</h1>
              <p style="margin: 0 0 24px 0; font-size: 16px; line-height: 24px; color: #4b5563; text-align: center;">
                Click the button below to sign in to your account.
              </p>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td align="center">
                    <a href="{{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=email" style="display: inline-block; padding: 14px 32px; background-color: #FF4500; color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600; border-radius: 9999px;">Sign In</a>
                  </td>
                </tr>
              </table>
              <p style="margin: 24px 0 0 0; font-size: 14px; line-height: 20px; color: #9ca3af; text-align: center;">
                This link expires in 1 hour. If you didn't request this, you can safely ignore this email.
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding: 24px 32px; border-top: 1px solid #f3f4f6; text-align: center;">
              <p style="margin: 0; font-size: 12px; color: #9ca3af;">
                Hunt - Find jobs you're actually likely to get.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
```

---

## 4. Change Email Address

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f9fafb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f9fafb;">
    <tr>
      <td align="center" style="padding: 40px 20px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 480px; background-color: #ffffff; border-radius: 12px; border: 1px solid #e5e7eb;">
          <!-- Header -->
          <tr>
            <td style="padding: 32px 32px 24px 32px; text-align: center; border-bottom: 1px solid #f3f4f6;">
              <img src="https://hunt.careers/paper.png" alt="Hunt" width="40" height="40" style="display: inline-block; vertical-align: middle;">
              <span style="display: inline-block; vertical-align: middle; margin-left: 8px; font-size: 24px; font-weight: 700; color: #000000;">hunt<span style="color: #FF4500;">.</span></span>
            </td>
          </tr>
          <!-- Content -->
          <tr>
            <td style="padding: 32px;">
              <h1 style="margin: 0 0 16px 0; font-size: 24px; font-weight: 600; color: #111827; text-align: center;">Confirm email change</h1>
              <p style="margin: 0 0 24px 0; font-size: 16px; line-height: 24px; color: #4b5563; text-align: center;">
                Click the button below to confirm changing your email to this address.
              </p>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td align="center">
                    <a href="{{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=email_change" style="display: inline-block; padding: 14px 32px; background-color: #FF4500; color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600; border-radius: 9999px;">Confirm Email Change</a>
                  </td>
                </tr>
              </table>
              <p style="margin: 24px 0 0 0; font-size: 14px; line-height: 20px; color: #9ca3af; text-align: center;">
                If you didn't request this change, please contact support immediately.
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding: 24px 32px; border-top: 1px solid #f3f4f6; text-align: center;">
              <p style="margin: 0; font-size: 12px; color: #9ca3af;">
                Hunt - Find jobs you're actually likely to get.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
```

---

## 5. Invite User

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f9fafb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f9fafb;">
    <tr>
      <td align="center" style="padding: 40px 20px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 480px; background-color: #ffffff; border-radius: 12px; border: 1px solid #e5e7eb;">
          <!-- Header -->
          <tr>
            <td style="padding: 32px 32px 24px 32px; text-align: center; border-bottom: 1px solid #f3f4f6;">
              <img src="https://hunt.careers/paper.png" alt="Hunt" width="40" height="40" style="display: inline-block; vertical-align: middle;">
              <span style="display: inline-block; vertical-align: middle; margin-left: 8px; font-size: 24px; font-weight: 700; color: #000000;">hunt<span style="color: #FF4500;">.</span></span>
            </td>
          </tr>
          <!-- Content -->
          <tr>
            <td style="padding: 32px;">
              <h1 style="margin: 0 0 16px 0; font-size: 24px; font-weight: 600; color: #111827; text-align: center;">You're invited to Hunt</h1>
              <p style="margin: 0 0 24px 0; font-size: 16px; line-height: 24px; color: #4b5563; text-align: center;">
                You've been invited to join Hunt. Click the button below to create your account.
              </p>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td align="center">
                    <a href="{{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=invite" style="display: inline-block; padding: 14px 32px; background-color: #FF4500; color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600; border-radius: 9999px;">Accept Invitation</a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding: 24px 32px; border-top: 1px solid #f3f4f6; text-align: center;">
              <p style="margin: 0; font-size: 12px; color: #9ca3af;">
                Hunt - Find jobs you're actually likely to get.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
```

---

## Optional: Email OTP Template (if you switch to passwordless login with 4-digit codes)

**Important:** Supabase defaults to 6-digit OTP codes. To use 4-digit codes, you would need to self-host Supabase or use a custom auth hook. The standard hosted Supabase uses 6-digit codes minimum for security reasons.

If you want to use OTP codes instead of links, replace the Magic Link template with:

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f9fafb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f9fafb;">
    <tr>
      <td align="center" style="padding: 40px 20px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 480px; background-color: #ffffff; border-radius: 12px; border: 1px solid #e5e7eb;">
          <!-- Header -->
          <tr>
            <td style="padding: 32px 32px 24px 32px; text-align: center; border-bottom: 1px solid #f3f4f6;">
              <img src="https://hunt.careers/paper.png" alt="Hunt" width="40" height="40" style="display: inline-block; vertical-align: middle;">
              <span style="display: inline-block; vertical-align: middle; margin-left: 8px; font-size: 24px; font-weight: 700; color: #000000;">hunt<span style="color: #FF4500;">.</span></span>
            </td>
          </tr>
          <!-- Content -->
          <tr>
            <td style="padding: 32px;">
              <h1 style="margin: 0 0 16px 0; font-size: 24px; font-weight: 600; color: #111827; text-align: center;">Your login code</h1>
              <p style="margin: 0 0 24px 0; font-size: 16px; line-height: 24px; color: #4b5563; text-align: center;">
                Enter this code to sign in to Hunt:
              </p>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td align="center">
                    <div style="display: inline-block; padding: 16px 32px; background-color: #f3f4f6; border-radius: 8px; font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #111827;">{{ .Token }}</div>
                  </td>
                </tr>
              </table>
              <p style="margin: 24px 0 0 0; font-size: 14px; line-height: 20px; color: #9ca3af; text-align: center;">
                This code expires in 5 minutes.
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding: 24px 32px; border-top: 1px solid #f3f4f6; text-align: center;">
              <p style="margin: 0; font-size: 12px; color: #9ca3af;">
                Hunt - Find jobs you're actually likely to get.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
```

---

## How to Apply These Templates

1. Go to your [Supabase Dashboard](https://supabase.com/dashboard)
2. Select your Hunt project
3. Navigate to **Authentication > Email Templates**
4. For each template type, paste the corresponding HTML above
5. Save changes

## URL Configuration

Make sure to configure your redirect URLs:
1. Go to **Authentication > URL Configuration**
2. Set **Site URL** to `https://hunt.careers`
3. Add `http://localhost:3000` to **Redirect URLs** for local development
