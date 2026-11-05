import axios from 'axios';
export const api=axios.create({baseURL:'/api/v1'});
export function errorMessage(error:unknown):string {if(axios.isAxiosError(error))return String(error.response?.data?.error?.message||error.message);return error instanceof Error?error.message:String(error);}
