import { useEffect, useState } from 'react';
import AdminConsole from './AdminConsole.jsx';
import './App.css';

const emptyForm = {
  firstName: '',
  lastName: '',
  email: '',
  password: '',
  confirmPassword: '',
  acceptedTerms: false,
};

async function readResponse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail[0]?.msg : data.detail;
    throw new Error(detail || 'The request could not be completed.');
  }
  return data;
}

export default function App() {
  const [formData, setFormData] = useState(emptyForm);
  const [mode, setMode] = useState('signup');
  const [loggedInUser, setLoggedInUser] = useState(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    let cancelled = false;

    fetch('/api/me')
      .then(async (response) => {
        if (response.status === 401) return null;
        return readResponse(response);
      })
      .then((data) => {
        if (!cancelled && data?.user) setLoggedInUser(data.user);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setAuthChecking(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const handleChange = (event) => {
    const { name, value, type, checked } = event.target;
    setFormData((previous) => ({
      ...previous,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setSuccess('');

    if (mode === 'signup') {
      if (formData.password !== formData.confirmPassword) {
        setError('Passwords do not match.');
        return;
      }
      if (!formData.acceptedTerms) {
        setError('Please accept the Terms of Use & Privacy Policy.');
        return;
      }
    }

    setLoading(true);
    try {
      const isLogin = mode === 'login';
      const data = await readResponse(
        await fetch(isLogin ? '/api/login' : '/api/signup', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(
            isLogin
              ? { email: formData.email, password: formData.password }
              : {
                  first_name: formData.firstName,
                  last_name: formData.lastName,
                  email: formData.email,
                  password: formData.password,
                  confirm_password: formData.confirmPassword,
                  accepted_terms: formData.acceptedTerms,
                },
          ),
        }),
      );

      if (isLogin) {
        setLoggedInUser(data.user);
        setFormData(emptyForm);
      } else {
        const email = formData.email;
        setFormData({ ...emptyForm, email });
        setMode('login');
        setSuccess(data.message || 'Your account is waiting for admin approval.');
      }
    } catch (requestError) {
      setError(requestError.message || 'The request could not be completed.');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await readResponse(await fetch('/api/logout', { method: 'POST' }));
      setLoggedInUser(null);
      setFormData(emptyForm);
      setMode('login');
      setError('');
      setSuccess('');
    } catch (logoutError) {
      setError(logoutError.message || 'Could not log out. Please try again.');
    }
  };

  if (authChecking) {
    return (
      <div className="signup-wrapper">
        <div className="signup-card">Checking your session…</div>
      </div>
    );
  }

  if (loggedInUser?.role === 'admin' || loggedInUser?.role === 'super_admin') {
    return <AdminConsole user={loggedInUser} onLogout={handleLogout} />;
  }

  if (loggedInUser) {
    return (
      <div className="signup-wrapper">
        <div className="signup-card">
          <p className="login-success">
            Welcome, {loggedInUser.first_name}. Your account is approved and you are
            logged in.
          </p>
          <button type="button" className="submit-btn logout-btn" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="signup-wrapper">
      <div className="signup-card">
        <div className="signup-header">
          <h1>{mode === 'signup' ? 'Sign Up' : 'Log In'}</h1>
          <p>
            {mode === 'signup'
              ? 'Create an account and wait for admin approval.'
              : 'Log in with your approved account.'}
          </p>
        </div>

        {error && <div className="alert alert-error">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        <form onSubmit={handleSubmit}>
          {mode === 'signup' && (
            <div className="form-row">
              <div className="form-group">
                <input
                  type="text"
                  name="firstName"
                  placeholder="First Name"
                  value={formData.firstName}
                  onChange={handleChange}
                  required
                />
              </div>
              <div className="form-group">
                <input
                  type="text"
                  name="lastName"
                  placeholder="Last Name"
                  value={formData.lastName}
                  onChange={handleChange}
                  required
                />
              </div>
            </div>
          )}

          <div className="form-group">
            <input
              type="email"
              name="email"
              placeholder="Email"
              value={formData.email}
              onChange={handleChange}
              required
            />
          </div>

          <div className="form-group">
            <input
              type="password"
              name="password"
              placeholder="Password"
              value={formData.password}
              onChange={handleChange}
              minLength={mode === 'signup' ? 8 : undefined}
              required
            />
          </div>

          {mode === 'signup' && (
            <>
              <div className="form-group">
                <input
                  type="password"
                  name="confirmPassword"
                  placeholder="Confirm Password"
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  minLength={8}
                  required
                />
              </div>

              <label className="checkbox-group">
                <input
                  type="checkbox"
                  name="acceptedTerms"
                  checked={formData.acceptedTerms}
                  onChange={handleChange}
                  required
                />
                <span>
                  I accept the <a href="#terms" onClick={(event) => event.preventDefault()}>Terms of Use</a>
                  {' '}&amp;{' '}
                  <a href="#privacy" onClick={(event) => event.preventDefault()}>Privacy Policy</a>
                </span>
              </label>
            </>
          )}

          <button type="submit" className="submit-btn" disabled={loading}>
            {loading
              ? mode === 'signup' ? 'Signing Up...' : 'Logging In...'
              : mode === 'signup' ? 'Sign Up' : 'Log In'}
          </button>
        </form>

        <p className="auth-switch">
          {mode === 'signup' ? 'Already have an account?' : 'Need a new account?'}{' '}
          <button
            type="button"
            onClick={() => {
              setMode(mode === 'signup' ? 'login' : 'signup');
              setError('');
              setSuccess('');
            }}
          >
            {mode === 'signup' ? 'Log in' : 'Sign up'}
          </button>
        </p>
      </div>
    </div>
  );
}
