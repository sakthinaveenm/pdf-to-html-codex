export const serif='"Folio Serif", "Folio Devanagari", "Folio Tamil", Georgia, "Nirmala UI", serif';
const fonts=[serif,'system-ui, "Noto Sans Devanagari", "Nirmala UI", sans-serif','ui-monospace, SFMono-Regular, Consolas, monospace'];
/** Preserve bounded document typography; reject pasted CSS URLs and arbitrary rules. */
export function cleanTypographyStyle(source:string|null):string|null{
 if(!source)return null;
 const result:string[]=[];
 for(const rule of source.split(';')){const index=rule.indexOf(':');if(index<0)continue;const name=rule.slice(0,index).trim().toLowerCase();let value=rule.slice(index+1).trim();let valid=false;
 if(name==='text-align')valid=['left','right','center','justify','start','end'].includes(value);
 else if(name==='font-family'){if(value==='serif')value=serif;value=fonts.find(font=>font.replace(/\s*,\s*/g,',')===value.replace(/\s*,\s*/g,','))||value;valid=fonts.includes(value);}
 else if(name==='font-size'){const m=value.match(/^(\d+(?:\.\d+)?)(em|px)$/);valid=!!m&&(m[2]==='em'?+m[1]>=.25&&+m[1]<=6:+m[1]>=8&&+m[1]<=96);}
 else if(name==='word-spacing'){const m=value.match(/^(-?\d+(?:\.\d+)?)rem$/);valid=!!m&&+m[1]>=-2&&+m[1]<=4;}
 else if(name==='display')valid=['block','inline-block'].includes(value);
 else if(name==='font-weight')valid=['400','500','600','700','800','900','normal','bold'].includes(value);
 else if(name==='font-style')valid=['normal','italic','oblique'].includes(value);
 else if(name==='line-height')valid=/^\d+(?:\.\d+)?$/.test(value)&&+value>=1&&+value<=2.5;
 else if(['margin-block-start','margin-block-end'].includes(name)){const m=value.match(/^(\d+(?:\.\d+)?)rem$/);valid=!!m&&+m[1]>=0&&+m[1]<=100;}
 else if(['color','background-color','border-color'].includes(name))valid=/^#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?$/.test(value);
 else if(name==='text-decoration')valid=['none','underline','line-through'].includes(value);
 else if(name==='text-indent'){const m=value.match(/^(\d+(?:\.\d+)?)em$/);valid=!!m&&+m[1]>=0&&+m[1]<=10;}
 else if(name==='list-style-position')valid=['inside','outside'].includes(value);
 else if(name==='white-space')valid=['normal','nowrap'].includes(value);
 else if(name==='font-stretch')valid=/^\d+(?:\.\d+)?%$/.test(value)&&parseFloat(value)>=62.5&&parseFloat(value)<=100;
 else if(name==='position')valid=value==='relative';
 else if(name==='z-index')valid=value==='1';
 else if(name==='border')valid=value==='0';
 else if(name==='border-collapse')valid=value==='collapse';
 else if(name==='table-layout')valid=value==='fixed';
 else if(name==='vertical-align')valid=value==='top';
 else if(['padding','padding-right','padding-left'].includes(name)){const m=value.match(/^(\d+(?:\.\d+)?)(rem|em)?$/);valid=!!m&&+m[1]<=100;}
 else if(['margin-left','margin-right'].includes(name)||(name==='width'&&value.endsWith('%'))){const m=value.match(/^(\d+(?:\.\d+)?)%$/);valid=!!m&&+m[1]<=100;}
 else if(name==='width'){const m=value.match(/^(\d+(?:\.\d+)?)em$/);valid=!!m&&+m[1]>0&&+m[1]<=60;}
 if(valid)result.push(`${name}: ${value}`);
 }
 return result.join('; ')||null;
}
