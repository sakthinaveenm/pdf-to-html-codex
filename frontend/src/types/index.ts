export interface Job {id:string;filename:string;status:string;progress:number;engine:string|null;error:string|null;createdAt:string;inspection:{pageCount:number}|null;options:{languages:string[];language:string}}
export interface JobList {items:Job[];total:number;counts:Record<string,number>}
export interface DocumentAST {documentId:string;revision:number;title:string;language:string;warnings:string[];pages:{page:number}[];blocks:{blockId:string;sourcePage:number|null;blockType:string;content:string}[]}
export interface Capabilities {converters:{name:string;installed:boolean}[];ocr:{languages:string[]};settings:{workers:number;device:string;maxUploadMB:number}}
