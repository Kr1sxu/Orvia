import React from 'react';

/** 品牌图形来自项目自有SVG；alt留空避免在旁边已有品牌名称时重复朗读。 */
export function BrandMark({className='brand-mark'}:{className?:string}) {
  return <img className={className} src={new URL('../../resources/icons/brand.svg',import.meta.url).href} alt="" aria-hidden="true"/>;
}
const paths={
  plus:'M12 5v14M5 12h14',
  settings:'M9 4h6l1 3 3 1v6l-3 1-1 3H9l-1-3-3-1V8l3-1zM15 11a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
  arrow:'M7 17 17 7M7 7h10v10',
  send:'M12 19V5M6 11l6-6 6 6',
  down:'M12 5v14M6 13l6 6 6-6',
} as const;
/** 功能图标只作装饰，可访问名称由按钮文字或aria-label提供，不以符号代替操作说明。 */
export function Icon({name}:{name:keyof typeof paths}) {
  return <svg className="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]}/></svg>;
}
