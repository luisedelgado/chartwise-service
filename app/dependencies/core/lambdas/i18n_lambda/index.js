const environment = process.env.ENVIRONMENT;

const verifyEmailEnglishTemplate = `
<div style="text-align: center; font-family: Arial, sans-serif;">
  <img
    src="https://chartwise-public-media.s3.us-east-2.amazonaws.com/logo.png"
    alt="ChartWise Logo"
    width="200"
    style="margin-bottom: 20px;"
  />

  <h2>Verify Your Email</h2>

  <p style="font-size: 16px;">Use the code below to verify your email address:</p>
  <p style="font-size: 24px; font-weight: bold; letter-spacing: 1px;">{##verify_code##}</p>

  <p style="font-size: 14px; color: #888; margin-top: 30px;">
    If you didn’t create a ChartWise account, you can ignore this email or contact support.
  </p>
</div>
`;

const forgotPasswordEnglishTemplate = `
<div style="text-align: center; font-family: Arial, sans-serif;">
  <img
    src="https://chartwise-public-media.s3.us-east-2.amazonaws.com/logo.png"
    alt="ChartWise Logo"
    width="200"
    style="margin-bottom: 20px;"
  />

  <h2>Reset Your Password</h2>

  <p style="font-size: 16px;">Use the code below to reset your password:</p>
  <p style="font-size: 24px; font-weight: bold; letter-spacing: 1px;">{##verify_code##}</p>

  <p style="font-size: 14px; color: #888; margin-top: 30px;">
    If you didn’t request a password reset, you can ignore this email or contact support.
  </p>
</div>
`;

const verifyEmailSpanishTemplate = `
<div style="text-align: center; font-family: Arial, sans-serif;">
  <img
    src="https://chartwise-public-media.s3.us-east-2.amazonaws.com/logo.png"
    alt="ChartWise Logo"
    width="200"
    style="margin-bottom: 20px;"
  />

  <h2>Verifica tu correo electrónico</h2>

  <p style="font-size: 16px;">Usa el siguiente código para verificar tu correo electrónico:</p>
  <p style="font-size: 24px; font-weight: bold; letter-spacing: 1px;">{##verify_code##}</p>

  <p style="font-size: 14px; color: #888; margin-top: 30px;">
    Si no creaste una cuenta en ChartWise, puedes ignorar este correo o contactar al equipo de soporte.
  </p>
</div>
`;

const forgotPasswordSpanishTemplate = `
<div style="text-align: center; font-family: Arial, sans-serif;">
  <img
    src="https://chartwise-public-media.s3.us-east-2.amazonaws.com/logo.png"
    alt="ChartWise Logo"
    width="200"
    style="margin-bottom: 20px;"
  />

  <h2>Restablecer contraseña</h2>

  <p style="font-size: 16px;">Usa el siguiente código para restablecer tu contraseña:</p>
  <p style="font-size: 24px; font-weight: bold; letter-spacing: 1px;">{##verify_code##}</p>

  <p style="font-size: 14px; color: #888; margin-top: 30px;">
    Si no solicitaste restablecer tu contraseña, puedes ignorar este correo o contactar al equipo de soporte.
  </p>
</div>
`;

exports.handler = async (event, context) => {
  const triggerSource = event.triggerSource;
  const userLanguage = (event.request.userAttributes['custom:language_preference'] || 'en').toLowerCase();

  if (triggerSource === 'CustomMessage_SignUp') {
    if (userLanguage.startsWith('en')) {
      event.response.emailMessage = verifyEmailEnglishTemplate.replace('{##verify_code##}', event.request.codeParameter);
      event.response.emailSubject = 'Verification code';
    }
    else if (userLanguage.startsWith('es')) {
      event.response.emailMessage = verifyEmailSpanishTemplate.replace('{##verify_code##}', event.request.codeParameter);
      event.response.emailSubject = 'Código de verificación';
    }
    else {
      throw new Error(`Missing handling of language ${userLanguage} in Cognito custom trigger leveraging i18n Lambda`);
    }
  }
  else if (triggerSource === 'CustomMessage_ForgotPassword') {
    const userEmail = event.request.userAttributes.email;
    const base64Email = Buffer.from(userEmail).toString('base64');

    if (userLanguage.startsWith('en')) {
      event.response.emailMessage = forgotPasswordEnglishTemplate.replace('{##verify_code##}', event.request.codeParameter);
      event.response.emailSubject = 'Reset your ChartWise password';
    }
    else if (userLanguage.startsWith('es')) {
      event.response.emailMessage = forgotPasswordSpanishTemplate.replace('{##verify_code##}', event.request.codeParameter);
      event.response.emailSubject = 'Restablece tu contraseña de ChartWise';
    }
    else {
      throw new Error(`Missing handling of language ${userLanguage} in Cognito custom trigger leveraging i18n Lambda`);
    }
  }
  else {
    console.log(`Unsupported trigger source: ${triggerSource}`);
  }
  return event;
};
