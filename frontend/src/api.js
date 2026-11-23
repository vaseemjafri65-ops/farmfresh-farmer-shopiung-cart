import axios from 'axios';
const api = axios.create({baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api'});
api.interceptors.request.use(config => { const token=localStorage.getItem('ff_admin_token'); if(token) config.headers.Authorization=`Bearer ${token}`; const sid=localStorage.getItem('ff_cart_id'); if(sid) config.headers['X-Cart-Id']=sid; return config; });
api.interceptors.response.use(r=>r,err=>Promise.reject(new Error(err.response?.data?.detail || 'Something went wrong. Please try again.')));
export default api;
