/*
import { useState } from 'react';
import './App.css';

export default function App() {
  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    email: '',
    password: '',
    confirmPassword: '',
    acceptedTerms: false,
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    if (!formData.acceptedTerms) {
      setError('Please accept the Terms of Use & Privacy Policy.');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          first_name: formData.firstName,
          last_name: formData.lastName,
          email: formData.email,
          password: formData.password,
          confirm_password: formData.confirmPassword,
          accepted_terms: formData.acceptedTerms,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        const detail = Array.isArray(data.detail)
          ? data.detail[0]?.msg
          : data.detail;
        throw new Error(detail || 'Failed to create account.');
      }

      setSuccess(`Welcome, ${data.user.first_name}! Your account has been created.`);
      setFormData({
        firstName: '',
        lastName: '',
        email: '',
        password: '',
        confirmPassword: '',
        acceptedTerms: false,
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="signup-wrapper">
      <div className="signup-card">
        <div className="signup-header">
          <h1>Sign Up</h1>
          <p>Please fill in this form to create an account!</p>
        </div>

        {error && <div className="alert alert-error">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        <form onSubmit={handleSubmit}>
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
              minLength={8}
              required
            />
          </div>

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
              I accept the <a href="#terms" onClick={(e) => e.preventDefault()}>Terms of Use</a> &amp;{' '}
              <a href="#privacy" onClick={(e) => e.preventDefault()}>Privacy Policy</a>
            </span>
          </label>

          <button type="submit" className="submit-btn" disabled={loading}>
            {loading ? 'Signing Up...' : 'Sign Up'}
          </button>
        </form>
      </div>
    </div>
  );
}
  */


import { useState } from 'react';
import './App.css';

const emptyForm = {
  firstName: '',
  lastName: '',
  email: '',
  password: '',
  confirmPassword: '',
  acceptedTerms: false,
};

export default function App() {
  const [formData, setFormData] = useState(emptyForm);
  const [mode, setMode] = useState('signup');
  const [loggedInUser, setLoggedInUser] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

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
      const response = await fetch(isLogin ? '/api/login' : '/api/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(
          isLogin
            ? {
                email: formData.email,
                password: formData.password,
              }
            : {
                first_name: formData.firstName,
                last_name: formData.lastName,
                email: formData.email,
                password: formData.password,
                confirm_password: formData.confirmPassword,
                accepted_terms: formData.acceptedTerms,
              },
        ),
      });

      const data = await response.json();

      if (!response.ok) {
        const detail = Array.isArray(data.detail)
          ? data.detail[0]?.msg
          : data.detail;
        throw new Error(detail || 'The request could not be completed.');
      }

      if (isLogin) {
        setLoggedInUser(data.user);
        setFormData(emptyForm);
      } else {
        const email = formData.email;
        setFormData({ ...emptyForm, email });
        setMode('login');
        setSuccess('Account created. Please log in with your email and password.');
      }
    } catch (requestError) {
      setError(requestError.message || 'The request could not be completed.');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    setLoggedInUser(null);
    setFormData(emptyForm);
    setMode('login');
    setError('');
    setSuccess('');
  };

  if (loggedInUser) {
    return (
      <div className="signup-wrapper">
        <div className="signup-card">
          <p className="login-success">
            You are logged in successfully because your credentials matched the database.
          </p>
          <button
            type="button"
            className="submit-btn logout-btn"
            onClick={handleLogout}
          >
            Logout
            <small>
              This is just for testing purposes. You can log out and check another
              account, or sign up with new credentials.
            </small>
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
              ? 'Please fill in this form to create an account!'
              : 'Log in with the email and password you used to sign up.'}
          </p>
        </div>

        {error && <div className="alert alert-error">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        <form onSubmit={handleSubmit}>
          {mode === 'signup' && (
            <>
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
            </>
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