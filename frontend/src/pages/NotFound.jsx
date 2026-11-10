import { Link } from 'react-router-dom';
import { EmptyState, PageHeader } from '../components/ui.jsx';

export default function NotFound() {
  return (
    <>
      <PageHeader title="Page not found" />
      <EmptyState title="There is nothing at this address">
        <Link to="/">Go to your home page</Link>
      </EmptyState>
    </>
  );
}
