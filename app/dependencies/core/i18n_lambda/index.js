// English template
const englishTemplate = `
<div style="text-align: center">
  <img
    src="https://bhpqrkshpqaaqwtemhgx.supabase.co/storage/v1/object/public/assets/email-logo.png"
  />
  
  <h2>Verification code</h2>

  <p>Hey, your Verification code is: {##verify_code##}</p>
</div>

`;

// Spanish template
const spanishTemplate = `
<div style="text-align: center">
  <img
    src="https://bhpqrkshpqaaqwtemhgx.supabase.co/storage/v1/object/public/assets/email-logo.png"
  />
  
  <h2>Código de verificación</h2>

  <p>Hola, tu código para verificación es: {##verify_code##}</p>
</div>
`;

exports.handler = async (event, context) => {
  // Get the user's preferred language
  // This could come from a custom attribute in Cognito
  const userLanguage = event.request.userAttributes['custom:language_preference'] || 'en';
  
  
  if (userLanguage === 'es') {
    event.response.emailMessage = spanishTemplate.replace('{##verify_code##}', event.request.codeParameter);
    event.response.emailSubject = 'Código de verificación';
  } else {
    // Default to English
    event.response.emailMessage = englishTemplate.replace('{##verify_code##}', event.request.codeParameter);
    event.response.emailSubject = 'Verification code';
  }
  
  return event;
};
