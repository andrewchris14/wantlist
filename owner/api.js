import {loadPublicIndex} from './index-loader.js';
export async function request(path,body){
 let response;
 try{response=await fetch(path,{credentials:'same-origin',cache:'no-store',headers:body?{'Content-Type':'application/json'}:{},...(body?{method:'POST',body:JSON.stringify(body)}:{})});}
 catch{throw Object.assign(Error('We couldn’t connect. Your change is not confirmed. Try again when you’re connected.'),{retry:true});}
 if(!response.ok){
  const message=response.status===401&&path==='/login'?'That PIN didn’t work. Please try again.':response.status===401?'This computer needs to be verified again. Enter your Owner PIN to continue.':response.status===409?(path==='/owner/category'?'Category could not be changed. It may contain listings, be protected, or have a duplicate name. Refresh before trying again.':'This set changed since you opened it. Open it again before making this change.'):response.status===429?'Please wait a little before trying to sign in again.':response.status===400?'This change couldn’t be saved. Check the entries and required confirmations.':'We couldn’t confirm your change. Please try again.';
  throw Object.assign(Error(message),{status:response.status,retry:response.status>=500,diagnostic:{route:path.split('?')[0],status:response.status,cf_ray:response.headers.get('CF-Ray'),server:response.headers.get('Server'),content_type:response.headers.get('Content-Type')}});
 }
 try{return await response.json();}
 catch{throw Object.assign(Error('We couldn’t read the result. Please try again.'),{retry:true});}
}
export async function publicRecords(){return loadPublicIndex(request);}
