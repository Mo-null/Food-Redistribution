import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { useAuth } from './auth.jsx';
import Layout from './components/Layout.jsx';
import { Loading } from './components/ui.jsx';
import Coordinator from './pages/Coordinator.jsx';
import DonationForm from './pages/DonationForm.jsx';
import Donations from './pages/Donations.jsx';
import Login from './pages/Login.jsx';
import NotFound from './pages/NotFound.jsx';
import Notifications from './pages/Notifications.jsx';
import Offers from './pages/Offers.jsx';
import Pickups from './pages/Pickups.jsx';
import Profile from './pages/Profile.jsx';
import Register from './pages/Register.jsx';

const HOME_BY_ROLE = {
  donor: '/donations',
  recipient: '/offers',
  coordinator: '/coordinator',
};

/** Lets signed-in users through, optionally only for the given roles. */
function Protected({ roles }) {
  const { user, ready } = useAuth();
  const location = useLocation();

  if (!ready) return <Loading />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />;
  return <Outlet />;
}

function Home() {
  const { user } = useAuth();
  return <Navigate to={HOME_BY_ROLE[user.role]} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      <Route element={<Protected />}>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="notifications" element={<Notifications />} />
          <Route path="profile" element={<Profile />} />

          <Route element={<Protected roles={['donor']} />}>
            <Route path="donations" element={<Donations />} />
            <Route path="donations/new" element={<DonationForm />} />
            <Route path="donations/:id/edit" element={<DonationForm />} />
            <Route path="pickups" element={<Pickups />} />
          </Route>

          <Route element={<Protected roles={['recipient']} />}>
            <Route path="offers" element={<Offers />} />
          </Route>

          <Route element={<Protected roles={['coordinator']} />}>
            <Route path="coordinator" element={<Coordinator />} />
          </Route>

          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>
    </Routes>
  );
}
