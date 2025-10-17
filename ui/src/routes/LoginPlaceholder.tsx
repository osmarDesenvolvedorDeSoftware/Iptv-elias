export default function LoginPlaceholder() {
  return (
    <form className="login-form">
      <label>
        Email
        <input name="email" type="email" autoComplete="username" />
      </label>
      <label>
        Senha
        <input name="password" type="password" autoComplete="current-password" />
      </label>
      <button type="submit">Entrar</button>
    </form>
  );
}
