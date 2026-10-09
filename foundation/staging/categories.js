import {hash} from './auth.js';
const fail=(code='INVALID')=>{const e=Error(code);e.code=code;throw e;};
export async function categories(db){return (await db.prepare('SELECT id,name,historical,revision FROM categories WHERE deleted_at IS NULL ORDER BY historical DESC,rowid').all()).results;}
export async function categoryMutation(db,input){
 if(!input||!/^[-\w]{16,100}$/.test(input.request_id||'')||!['create','rename','remove'].includes(input.op))fail();
 const digest=await hash(JSON.stringify(input)),receipt=await db.prepare('SELECT request_sha256,result_json FROM category_receipts WHERE id=?').bind(input.request_id).first();
 if(receipt){if(receipt.request_sha256!==digest)fail('CONFLICT');return {...JSON.parse(receipt.result_json),replayed:true};}
 if(!(await db.prepare('SELECT completed FROM staging_import_state WHERE id=1').first())?.completed)fail('CONFLICT');
 const name=typeof input.name==='string'?input.name.trim():null;if(input.op!=='remove'&&(typeof name!=='string'||!name||name.length>100))fail();
 const prior=input.op==='create'?null:await db.prepare('SELECT * FROM categories WHERE id=? AND deleted_at IS NULL').bind(input.id).first();
 if(input.op!=='create'&&(!prior||prior.historical||prior.revision!==input.revision))fail('CONFLICT');
 const id=prior?.id||'owner-category-'+crypto.randomUUID(),stamp=new Date().toISOString(),result={saved:true,id,revision:(prior?.revision||0)+1};
 const statements=[db.prepare(`INSERT INTO category_receipts VALUES(?,?,CASE WHEN ?='create' OR EXISTS(SELECT 1 FROM categories WHERE id=? AND revision=? AND historical=0 AND deleted_at IS NULL) THEN 1 ELSE 0 END,?,?)`).bind(input.request_id,digest,input.op,id,input.revision||0,JSON.stringify(result),stamp)];
 if(input.op==='create')statements.push(db.prepare('INSERT INTO categories VALUES(?,?,0,1,NULL)').bind(id,name));
 else if(input.op==='remove')statements.push(db.prepare('UPDATE categories SET deleted_at=?,revision=revision+1 WHERE id=?').bind(stamp,id));
 else {
  statements.push(db.prepare('UPDATE categories SET name=?,revision=revision+1 WHERE id=?').bind(name,id));
  statements.push(db.prepare(`INSERT INTO change_history SELECT 'category-rename-'||?||'-'||id,id,NULL,'owner','category_rename',json_object('metadata',json_object('display_category',?)),json_object('metadata',json_object('display_category',?),'_record_revision',revision+1),? FROM records WHERE json_extract(content_json,'$.display_category')=?`).bind(input.request_id,prior.name,name,stamp,prior.name));
  statements.push(db.prepare(`UPDATE public_records SET public_json=json_set(public_json,'$.display_category',?,'$.revision',revision+1,'$.updated_at',?),revision=revision+1,updated_at=? WHERE record_id IN (SELECT id FROM records WHERE json_extract(content_json,'$.display_category')=?)`).bind(name,stamp,stamp,prior.name));
  statements.push(db.prepare(`UPDATE records SET content_json=json_set(content_json,'$.display_category',?),revision=revision+1,updated_at=? WHERE json_extract(content_json,'$.display_category')=?`).bind(name,stamp,prior.name));
 }
 statements.push(db.prepare('INSERT INTO category_history VALUES(?,?,?,?,?,?)').bind(crypto.randomUUID(),id,input.op,JSON.stringify(prior?{name:prior.name,revision:prior.revision}:{}),JSON.stringify({name:input.op==='remove'?prior.name:name,deleted:input.op==='remove',revision:result.revision}),stamp));
 try{await db.batch(statements);}catch(e){const saved=await db.prepare('SELECT request_sha256,result_json FROM category_receipts WHERE id=?').bind(input.request_id).first();if(saved?.request_sha256===digest)return {...JSON.parse(saved.result_json),replayed:true};if(/constraint|Unknown category|Category contains|Historical category/i.test(e.message))fail('CONFLICT');throw e;}
 return result;
}
