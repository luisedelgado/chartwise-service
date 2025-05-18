exports.handler = async (event, context) => {
  const triggerSource = event.triggerSource;
  const userLanguage = (event.request.userAttributes['custom:language_preference'] || 'en').toLowerCase();

  const templates = {
    en: {
      verificationSubject: "Verification code",
      verificationBody: `
        <div style="text-align: center">
          <img width="400px" src="https://chartwise-public-media.s3.us-east-2.amazonaws.com/logo.png" />
          <h2>Verification code</h2>
          <p>Hey, your Verification code is: {##verify_code##}</p>
        </div>
      `,
      forgotPasswordSubject: "Reset your ChartWise password",
      forgotPasswordBody: `
        <div style="text-align: center">
          <img width="400px" src="https://chartwise-public-media.s3.us-east-2.amazonaws.com/logo.png" />
          <h2>Reset Password</h2>
          <p>Use this code to reset your password: {##verify_code##}</p>
        </div>
      `,
    },
    es: {
      verificationSubject: "Código de verificación",
      verificationBody: `
        <div style="text-align: center">
          <img width="400px" src="https://chartwise-public-media.s3.us-east-2.amazonaws.com/logo.png" />
          <h2>Código de verificación</h2>
          <p>Hola, tu código para verificación es: {##verify_code##}</p>
        </div>
      `,
      forgotPasswordSubject: "Restablece tu contraseña de ChartWise",
      forgotPasswordBody: `
        <div style="text-align: center">
          <img width="400px" src="https://chartwise-public-media.s3.us-east-2.amazonaws.com/logo.png" />
          <h2>Restablecer contraseña</h2>
          <p>Usa este código para restablecer tu contraseña: {##verify_code##}</p>
        </div>
      `,
    },
  };

  const t = userLanguage.startsWith('es') ? templates.es : templates.en;

  if (triggerSource === 'CustomMessage_SignUp') {
    event.response.emailSubject = t.verificationSubject;
    event.response.emailMessage = t.verificationBody.replace('{##verify_code##}', event.request.codeParameter);
  } else if (triggerSource === 'CustomMessage_ForgotPassword') {
    event.response.emailSubject = t.forgotPasswordSubject;
    event.response.emailMessage = t.forgotPasswordBody.replace('{##verify_code##}', event.request.codeParameter);
  }

  return event;
};
