import {BrowserRouter,Routes,Route,Link,Navigate} from 'react-router-dom';
import {Dashboard} from './screens/Dashboard';
export default function App(){return <BrowserRouter><header className="app-header"><Link className="brand" to="/">PDF → HTML</Link><a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">API docs ↗</a></header><main><Routes><Route path="/" element={<Dashboard/>}/><Route path="/documents/:id" element={<Navigate to="/" replace/>}/><Route path="*" element={<p>Page not found. <Link to="/">Return to workspace</Link></p>}/></Routes></main></BrowserRouter>}
