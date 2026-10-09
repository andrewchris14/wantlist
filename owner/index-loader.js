// Load the collection atomically: a failed or malformed page never publishes a
// partial collection. Detect cursor cycles/overlap instead of consuming quota.
export async function loadPublicIndex(request){
 const records=[],ids=new Set(),cursors=new Set();let after='',pageNumber=0;
 do{
  pageNumber++;
  let page;
  try{page=await request('/public/index?after='+encodeURIComponent(after));}
  catch(error){error.indexPage={number:pageNumber,after};throw error;}
  if(!page||!Array.isArray(page.records)||page.records.length>500||
     !(page.next===null||typeof page.next==='string'&&page.next.length>0))throw invalid(pageNumber,after);
  for(const record of page.records){
   if(!record||typeof record.id!=='string'||!record.id||ids.has(record.id))throw invalid(pageNumber,after);
   ids.add(record.id);records.push(record);
  }
  if(page.next!==null){
   if(!page.records.length||page.next!==page.records.at(-1).id||page.next===after||cursors.has(page.next))throw invalid(pageNumber,after);
   cursors.add(page.next);
  }
  after=page.next;
 }while(after!==null);
 return records;
}
function invalid(number,after){return Object.assign(Error('The list could not be loaded completely. Please try again.'),{retry:true,indexPage:{number,after},code:'INVALID_INDEX_PAGE'});}
