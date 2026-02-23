def signup_verification_template(username: str, otp: str):
    subject = "Welcome to MILA 💌 Verify Your Email"

    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 12px;">
            
            <h2 style="color: #333;">Hi {username},</h2>

            <p style="font-size: 15px; color: #555;">
                We’re so excited to have you on <strong>MILA</strong>! 💛
            </p>

            <p style="font-size: 15px; color: #555;">
                To complete your signup and start connecting, please use the verification code below:
            </p>

            <div style="text-align: center; margin: 25px 0;">
                <h1 style="letter-spacing: 6px; font-size: 32px; color: #E91E63;">
                    {otp}
                </h1>
            </div>

            <p style="font-size: 14px; color: #777;">
                This code is valid for 5 minutes. For your security, please don’t share it with anyone.
            </p>

            <p style="font-size: 14px; color: #777;">
                If you didn’t sign up for MILA, you can safely ignore this email.
            </p>

            <p style="margin-top: 25px; font-size: 14px; color: #999;">
                See you inside 😉<br/>
                — Team MILA
            </p>

        </div>
    </body>
    </html>
    """
    return subject, body

def login_verification_template(username: str, otp: str):
    subject = "Your MILA Login Code 💫"

    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f9f9f9;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 12px;">

            <h2>Hi {username},</h2>

            <p>Here’s your login verification code:</p>

            <div style="text-align:center; margin: 20px 0;">
                <h1 style="letter-spacing: 6px; color: #E91E63;">
                    {otp}
                </h1>
            </div>

            <p>This code will expire in 5 minutes.</p>

            <p>If this wasn’t you, please secure your account right away.</p>

            <p style="margin-top: 25px;">
                Let’s get you back to matching 💕<br/>
                — Team MILA
            </p>

        </div>
    </body>
    </html>
    """
    return subject, body

def reset_password_otp_template(username: str, otp: str):
    subject = "Reset Your MILA Password 🔐"

    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f9f9f9;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 12px;">

            <h2>Hi {username},</h2>

            <p>We received a request to reset your MILA password.</p>

            <p>Your password reset code is:</p>

            <div style="text-align:center; margin: 20px 0;">
                <h1 style="letter-spacing: 6px; color: #E91E63;">
                    {otp}
                </h1>
            </div>

            <p>This code is valid for 5 minutes.</p>

            <p>If you didn’t request this, you can ignore this email — your account is still safe.</p>

            <p style="margin-top: 25px;">
                Let’s get you back to connecting 💌<br/>
                — Team MILA
            </p>

        </div>
    </body>
    </html>
    """
    return subject, body

def onboarding_completed_template(username: str):
    subject = "You’re All Set on MILA 🎉"

    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 12px;">

            <h2>Hi {username},</h2>

            <p>Your profile setup is complete — and you’re officially ready to explore MILA!</p>

            <p>
                Start discovering matches, making connections, and seeing where things go ✨
            </p>

            <p>
                Your next great conversation might be just a swipe away 😉
            </p>

            <p style="margin-top: 25px;">
                Enjoy the journey 💕<br/>
                — Team MILA
            </p>

        </div>
    </body>
    </html>
    """

    return subject, body

def verification_approved_template(username: str):
    subject = "You’re Verified on MILA ✅✨"

    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 12px;">

            <h2>Hi {username},</h2>

            <p>Great news! 🎉 Your profile has been successfully approved.</p>

            <p>
                You now have access to many features on MILA — so go ahead and start connecting with confidence.
            </p>

            <p>
                Your story starts now 💫
            </p>

            <p style="margin-top: 25px;">
                — Team MILA
            </p>

        </div>
    </body>
    </html>
    """

    return subject, body

def verification_rejected_template(username: str):
    subject = "Profile Verification Update"

    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 12px;">

            <h2>Hi {username},</h2>

            <p>
                Thanks for submitting your profile for verification.
            </p>

            <p>
                Unfortunately, we weren’t able to approve it at this time. Please review your submitted details and make sure all information and photos meet our guidelines before reapplying.
            </p>

            <p>
                We’re here to help you get verified and start connecting soon 💛
            </p>

            <p style="margin-top: 25px;">
                — Team MILA
            </p>

        </div>
    </body>
    </html>
    """

    return subject, body
