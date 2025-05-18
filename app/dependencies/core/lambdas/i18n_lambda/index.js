const verifyEmailEnglishTemplate = `
<div style="text-align: center">
  <img
    src="https://chartwise-public-media.s3.us-east-2.amazonaws.com/logo.png"
  />
  
  <h2>Verification code</h2>

  <p>Hey, your Verification code is: {##verify_code##}</p>
</div>

`;

const forgotPasswordEnglishTemplate = `
<div style="text-align: center">
  <img
    src="https://chartwise-public-media.s3.us-east-2.amazonaws.com/logo.png"
  />
  
  <h2>Reset Password</h2>

  <p>Use this code to reset your password: {##verify_code##}</p>
</div>
`;

const verifyEmailSpanishTemplate = `
<div style="text-align: center">
  <img
    src="https://chartwise-public-media.s3.us-east-2.amazonaws.com/logo.png"
  />
  
  <h2>Código de verificación</h2>

  <p>Hola, tu código para verificación es: {##verify_code##}</p>
</div>
`;

const forgotPasswordSpanishTemplate = `
<div style="text-align: center">
  <img
    src="https://chartwise-public-media.s3.us-east-2.amazonaws.com/logo.png"
  />
  
  <h2>Restablecer contraseña</h2>

  <p>Usa este código para restablecer tu contraseña: {##verify_code##}</p>
</div>
`;

exports.handler = async (event, context) => {
  const triggerSource = event.triggerSource;
  const userLanguage = (event.request.userAttributes['custom:language_preference'] || 'en').toLowerCase();

  if (userLanguage.startsWith('es')) {
    if (triggerSource === 'CustomMessage_SignUp') {
      console.log("ZIZOU1111")
      console.log(event.request)
      event.response.emailMessage = verifyEmailSpanishTemplate.replace('{##verify_code##}', event.request.codeParameter);
      event.response.emailSubject = 'Código de verificación';
    }
    else if (triggerSource === 'CustomMessage_ForgotPassword') {
      console.log("ZIZOU2222")
      console.log(event.request)
      event.response.emailMessage = forgotPasswordSpanishTemplate.replace('{##verify_code##}', event.request.codeParameter);
      event.response.emailSubject = 'Restablece tu contraseña de ChartWise';
    }
  }
  else if (userLanguage.startsWith('en')) {
    if (triggerSource === 'CustomMessage_SignUp') {
      console.log("ZIZOU3333")
      console.log(event.request)
      event.response.emailMessage = verifyEmailEnglishTemplate.replace('{##verify_code##}', event.request.codeParameter);
      event.response.emailSubject = 'Verification code';
    }
    else if (triggerSource === 'CustomMessage_ForgotPassword') {
      console.log("ZIZOU44444")
      console.log(event.request)
      event.response.emailMessage = forgotPasswordEnglishTemplate.replace('{##verify_code##}', event.request.codeParameter);
      event.response.emailSubject = 'Reset your ChartWise password';
    }
  }
  else {
    throw new Error(`Missing handling of language ${userLanguage} in Cognito custom trigger leveraging i18n Lambda`);
  }
  return event;
};
