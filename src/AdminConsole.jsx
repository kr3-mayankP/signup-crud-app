import { useEffect, useState } from 'react';

async function readResponse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail[0]?.msg : data.detail;
    throw new Error(detail || 'The request could not be completed.');
  }
  return data;
}

export default function AdminConsole({ user, onLogout }) {
  const [requests, setRequests] = useState([]);
  const [userAccounts, setUserAccounts] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [selectedRoles, setSelectedRoles] = useState({});
  const [accountRoleDrafts, setAccountRoleDrafts] = useState({});
  const [loadingRequests, setLoadingRequests] = useState(true);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [loadingAccounts, setLoadingAccounts] = useState(true);
  const [busyUserId, setBusyUserId] = useState(null);
  const [busyRevokeId, setBusyRevokeId] = useState(null);
  const [busyAccountId, setBusyAccountId] = useState(null);
  const [requestError, setRequestError] = useState('');
  const [userError, setUserError] = useState('');
  const [accountError, setAccountError] = useState('');
  const [success, setSuccess] = useState('');

  const loadRequests = async () => {
    setRequestError('');
    setLoadingRequests(true);
    try {
      const data = await readResponse(await fetch('/api/admin/approval-requests'));
      setRequests(data.requests || []);
    } catch (requestError) {
      setRequestError(requestError.message || 'Could not load approval requests.');
    } finally {
      setLoadingRequests(false);
    }
  };

  const loadAccounts = async () => {
    if (user.role !== 'super_admin') return;
    setAccountError('');
    setLoadingAccounts(true);
    try {
      const data = await readResponse(await fetch('/api/super-admin/accounts'));
      const nextAccounts = data.accounts || [];
      setAccounts(nextAccounts);
      setAccountRoleDrafts(
        Object.fromEntries(nextAccounts.map((account) => [account.id, account.role])),
      );
    } catch (requestError) {
      setAccountError(requestError.message || 'Could not load accounts.');
    } finally {
      setLoadingAccounts(false);
    }
  };

  const loadUsers = async () => {
    if (user.role !== 'admin') return;
    setUserError('');
    setLoadingUsers(true);
    try {
      const data = await readResponse(await fetch('/api/users'));
      setUserAccounts(data.users || []);
    } catch (requestError) {
      setUserError(requestError.message || 'Could not load user accounts.');
    } finally {
      setLoadingUsers(false);
    }
  };

  useEffect(() => {
    loadRequests();
    loadAccounts();
    loadUsers();
  }, [user.role]);

  const approve = async (request) => {
    const role = user.role === 'super_admin'
      ? selectedRoles[request.id] || 'user'
      : 'user';

    setBusyUserId(request.id);
    setRequestError('');
    setSuccess('');
    try {
      await readResponse(
        await fetch(`/api/admin/users/${request.id}/approve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ role }),
        }),
      );
      setSuccess(`${request.email} approved as ${role}.`);
      await loadRequests();
      await loadAccounts();
    } catch (requestError) {
      setRequestError(requestError.message || 'Could not approve this account.');
    } finally {
      setBusyUserId(null);
    }
  };

  const reject = async (request) => {
    setBusyUserId(request.id);
    setRequestError('');
    setSuccess('');
    try {
      await readResponse(
        await fetch(`/api/admin/users/${request.id}/reject`, { method: 'POST' }),
      );
      setSuccess(`${request.email} rejected.`);
      await loadRequests();
      await loadAccounts();
    } catch (requestError) {
      setRequestError(requestError.message || 'Could not reject this account.');
    } finally {
      setBusyUserId(null);
    }
  };

  const revokeUserAccess = async (account) => {
    if (!window.confirm(`Revoke application access for ${account.email}?`)) return;

    setBusyRevokeId(account.id);
    setUserError('');
    setSuccess('');
    try {
      await readResponse(
        await fetch(`/api/admin/users/${account.id}/revoke`, { method: 'POST' }),
      );
      setSuccess(`Access revoked for ${account.email}.`);
      await loadUsers();
    } catch (requestError) {
      setUserError(requestError.message || 'Could not revoke this user access.');
    } finally {
      setBusyRevokeId(null);
    }
  };

  const saveRole = async (account) => {
    const role = accountRoleDrafts[account.id] || account.role;
    if (role === account.role) return;

    setBusyAccountId(account.id);
    setAccountError('');
    setSuccess('');
    try {
      await readResponse(
        await fetch(`/api/super-admin/accounts/${account.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ role }),
        }),
      );
      setSuccess(`${account.email} is now ${role.replace('_', ' ')}.`);
      await loadAccounts();
    } catch (requestError) {
      setAccountError(requestError.message || 'Could not change this account role.');
    } finally {
      setBusyAccountId(null);
    }
  };

  const changeAccess = async (account) => {
    const approvalStatus = account.approval_status === 'approved'
      ? 'revoked'
      : 'approved';

    if (
      approvalStatus === 'revoked'
      && !window.confirm(`Revoke application access for ${account.email}?`)
    ) {
      return;
    }

    setBusyAccountId(account.id);
    setAccountError('');
    setSuccess('');
    try {
      await readResponse(
        await fetch(`/api/super-admin/accounts/${account.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ approval_status: approvalStatus }),
        }),
      );
      setSuccess(
        approvalStatus === 'approved'
          ? `Access granted to ${account.email}.`
          : `Access revoked for ${account.email}.`,
      );
      await loadAccounts();
    } catch (requestError) {
      setAccountError(requestError.message || 'Could not change account access.');
    } finally {
      setBusyAccountId(null);
    }
  };

  return (
    <div className="signup-wrapper admin-wrapper">
      <div className="signup-card admin-card">
        <div className="admin-heading">
          <div className="signup-header">
            <h1>{user.role === 'super_admin' ? 'Super Admin Console' : 'Approval Requests'}</h1>
            <p>
              Signed in as {user.email} ({user.role.replace('_', ' ')}).
            </p>
          </div>
          <button type="button" className="secondary-btn" onClick={onLogout}>
            Logout
          </button>
        </div>

        {success && <div className="alert alert-success">{success}</div>}

        <section className="admin-section">
          <div className="request-toolbar">
            <p>Accounts waiting for approval</p>
            <button
              type="button"
              className="secondary-btn"
              onClick={loadRequests}
              disabled={loadingRequests}
            >
              Refresh
            </button>
          </div>

          {requestError && <div className="alert alert-error">{requestError}</div>}
          {loadingRequests ? (
            <p className="empty-state">Loading requests...</p>
          ) : requests.length === 0 ? (
            <p className="empty-state">There are no pending approval requests.</p>
          ) : (
            <div className="request-table-wrap">
              <table className="request-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Requested</th>
                    {user.role === 'super_admin' && <th>Grant role</th>}
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {requests.map((request) => (
                    <tr key={request.id}>
                      <td>{request.first_name} {request.last_name}</td>
                      <td>{request.email}</td>
                      <td>
                        {request.created_at
                          ? new Date(request.created_at).toLocaleDateString()
                          : '-'}
                      </td>
                      {user.role === 'super_admin' && (
                        <td>
                          <select
                            className="role-select"
                            value={selectedRoles[request.id] || 'user'}
                            onChange={(event) =>
                              setSelectedRoles((previous) => ({
                                ...previous,
                                [request.id]: event.target.value,
                              }))
                            }
                            disabled={busyUserId === request.id}
                          >
                            <option value="user">User</option>
                            <option value="admin">Admin</option>
                          </select>
                        </td>
                      )}
                      <td className="request-actions">
                        <button
                          type="button"
                          className="approve-btn"
                          onClick={() => approve(request)}
                          disabled={busyUserId === request.id}
                        >
                          Approve
                        </button>
                        <button
                          type="button"
                          className="reject-btn"
                          onClick={() => reject(request)}
                          disabled={busyUserId === request.id}
                        >
                          Reject
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {user.role === 'admin' && (
          <section className="admin-section">
            <div className="request-toolbar">
              <p>User accounts</p>
              <button
                type="button"
                className="secondary-btn"
                onClick={loadUsers}
                disabled={loadingUsers}
              >
                Refresh
              </button>
            </div>

            {userError && <div className="alert alert-error">{userError}</div>}
            {loadingUsers ? (
              <p className="empty-state">Loading users...</p>
            ) : userAccounts.length === 0 ? (
              <p className="empty-state">No user accounts found.</p>
            ) : (
              <div className="request-table-wrap">
                <table className="request-table account-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Access</th>
                      <th>Created</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {userAccounts.map((account) => (
                      <tr key={account.id}>
                        <td>{account.first_name} {account.last_name}</td>
                        <td>{account.email}</td>
                        <td>
                          <span className={`access-status status-${account.approval_status}`}>
                            {account.approval_status.replace('_', ' ')}
                          </span>
                        </td>
                        <td>
                          {account.created_at
                            ? new Date(account.created_at).toLocaleDateString()
                            : '-'}
                        </td>
                        <td className="account-actions">
                          {account.approval_status === 'approved' ? (
                            <button
                              type="button"
                              className="reject-btn"
                              onClick={() => revokeUserAccess(account)}
                              disabled={busyRevokeId === account.id}
                            >
                              Revoke access
                            </button>
                          ) : (
                            <span className="access-action-note">No active access</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {user.role === 'super_admin' && (
          <section className="admin-section accounts-section">
            <div className="request-toolbar">
              <p>All accounts</p>
              <button
                type="button"
                className="secondary-btn"
                onClick={loadAccounts}
                disabled={loadingAccounts}
              >
                Refresh
              </button>
            </div>

            {accountError && <div className="alert alert-error">{accountError}</div>}
            {loadingAccounts ? (
              <p className="empty-state">Loading accounts...</p>
            ) : accounts.length === 0 ? (
              <p className="empty-state">No accounts found.</p>
            ) : (
              <div className="request-table-wrap">
                <table className="request-table account-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Role</th>
                      <th>Access</th>
                      <th>Created</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accounts.map((account) => {
                      const draftRole = accountRoleDrafts[account.id] || account.role;
                      const busy = busyAccountId === account.id;
                      const isSelf = account.id === user.id;

                      return (
                        <tr key={account.id}>
                          <td>{account.first_name} {account.last_name}</td>
                          <td>{account.email}</td>
                          <td>
                            <select
                              className="role-select"
                              value={draftRole}
                              onChange={(event) =>
                                setAccountRoleDrafts((previous) => ({
                                  ...previous,
                                  [account.id]: event.target.value,
                                }))
                              }
                              disabled={busy || isSelf}
                              aria-label={`Role for ${account.email}`}
                            >
                              <option value="user">User</option>
                              <option value="admin">Admin</option>
                              <option value="super_admin">Super admin</option>
                            </select>
                          </td>
                          <td>
                            <span className={`access-status status-${account.approval_status}`}>
                              {account.approval_status.replace('_', ' ')}
                            </span>
                          </td>
                          <td>
                            {account.created_at
                              ? new Date(account.created_at).toLocaleDateString()
                              : '-'}
                          </td>
                          <td className="account-actions">
                            <button
                              type="button"
                              className="secondary-btn"
                              onClick={() => saveRole(account)}
                              disabled={busy || isSelf || draftRole === account.role}
                            >
                              Save role
                            </button>
                            <button
                              type="button"
                              className={account.approval_status === 'approved' ? 'reject-btn' : 'approve-btn'}
                              onClick={() => changeAccess(account)}
                              disabled={busy || isSelf}
                            >
                              {account.approval_status === 'approved'
                                ? 'Revoke access'
                                : 'Grant access'}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
