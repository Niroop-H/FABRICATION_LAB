// Procedural representative cleanroom. No external geometry or OEM assets.
export async function createScene(container, tools, onInteract) {
 const THREE = await import('https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js');
 const scene=new THREE.Scene(); scene.background=new THREE.Color(0xa9c2cf); scene.fog=new THREE.Fog(0xa9c2cf,28,65);
 const renderer=new THREE.WebGLRenderer({antialias:true}); renderer.setPixelRatio(Math.min(devicePixelRatio,1.5)); renderer.shadowMap.enabled=true; renderer.shadowMap.type=THREE.PCFSoftShadowMap; container.append(renderer.domElement);
 const camera=new THREE.PerspectiveCamera(58,1,.1,100); scene.add(new THREE.HemisphereLight(0xeaffff,0x647986,2.7));
 const sun=new THREE.DirectionalLight(0xffffff,3); sun.position.set(5,18,9); sun.castShadow=true; sun.shadow.mapSize.set(1024,1024); Object.assign(sun.shadow.camera,{left:-20,right:20,top:20,bottom:-20}); scene.add(sun);
 const mats={white:new THREE.MeshStandardMaterial({color:0xdbe6e9,roughness:.45,metalness:.25}),dark:new THREE.MeshStandardMaterial({color:0x213b4c,roughness:.5,metalness:.5}),metal:new THREE.MeshStandardMaterial({color:0x8fa9b3,roughness:.3,metalness:.7}),cyan:new THREE.MeshStandardMaterial({color:0x3ccfb5,emissive:0x14574a}),glass:new THREE.MeshStandardMaterial({color:0x4a9fb9,transparent:true,opacity:.5,roughness:.1})};
 function box(group,x,y,z,w,h,d,mat){const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),mat);m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;group.add(m);return m;}
 function cylinder(group,x,y,z,r,h,mat){const m=new THREE.Mesh(new THREE.CylinderGeometry(r,r,h,28),mat);m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;group.add(m);return m;}
 const floor=box(scene,0,-.12,0,29,.2,30,new THREE.MeshStandardMaterial({color:0xb1c5cc,roughness:.75})); floor.castShadow=false;
 const grid=new THREE.GridHelper(28,28,0x829ea8,0x95aeb7);grid.position.y=.005;scene.add(grid);
 box(scene,0,.015,2,3,.015,24,new THREE.MeshStandardMaterial({color:0x78acb7,roughness:.9}));
 box(scene,-14.4,2,0,.2,4,30,mats.white);box(scene,14.4,2,0,.2,4,30,mats.white);box(scene,0,2,-14.5,29,4,.2,mats.white);
 for(let x=-12;x<=12;x+=6){box(scene,x,4,-7,.15,.2,15,mats.metal);box(scene,x,3.8,-7,1.1,.05,5,new THREE.MeshBasicMaterial({color:0xe9ffff}));}
 // Overhead material transport rail on 300 mm profiles; shown via setProfile.
 const rail=new THREE.Group();scene.add(rail);box(rail,0,3.3,0,19,.12,.18,mats.dark);box(rail,-9,3.3,0,.18,.12,18,mats.dark);box(rail,9,3.3,0,.18,.12,18,mats.dark);
 const oht=box(rail,0,3,0,.8,.5,.8,mats.white);
 const machineObjects={},colliders=[];
 function label(text,x,y,z){const canvas=document.createElement('canvas');canvas.width=512;canvas.height=96;const ctx=canvas.getContext('2d');ctx.fillStyle='#102e41';ctx.fillRect(0,0,512,96);ctx.fillStyle='#c9fff0';ctx.font='bold 26px sans-serif';ctx.textAlign='center';ctx.fillText(text,256,58);const sp=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(canvas),depthTest:true}));sp.position.set(x,y,z);sp.scale.set(3.4,.64,1);scene.add(sp);}
 for(const [key,t] of Object.entries(tools)){
   const g=new THREE.Group();g.position.set(t.x,0,t.z);scene.add(g);let w=2.6,d=2.1;
   if(key==='gown'){box(g,0,1,0,2.6,2,.4,mats.white);box(g,0,2.3,0,3,.2,.8,mats.dark);}
   else if(key==='facilities'){for(let i=-1;i<=1;i++){cylinder(g,i,.9,0,.32,1.8,mats.metal);box(g,i,2.1,0,.1,.6,.1,mats.cyan);}}
   else if(key==='stock'){box(g,0,1.4,0,2.4,2.8,1.3,mats.dark);for(let y=.4;y<2.7;y+=.7){box(g,0,y,.25,2.2,.08,1.1,mats.metal);for(let x=-.7;x<1;x+=1.4)box(g,x,y+.25,.35,.65,.45,.6,mats.white);}}
   else if(key==='oxidation'||key==='anneal'){box(g,0,.55,0,2.7,1.1,2,mats.white);for(let i=-.7;i<=.8;i+=.7){const tube=cylinder(g,i,1.7,0,.3,1.6,mats.metal);box(g,i,1.5,.32,.35,1,.08,mats.glass);}box(g,0,2.6,0,2.8,.25,2,mats.white);}
   else if(key==='etch'||key==='deposition'){cylinder(g,0,.6,0,1.1,1.2,mats.dark);cylinder(g,0,1.5,0,.95,.6,mats.white);cylinder(g,0,1.9,0,.6,.18,mats.metal);box(g,1,1.15,.7,.7,1.3,.8,mats.white);box(g,-.65,1,.85,.7,.08,.6,mats.metal);}
   else if(key==='lithography'){w=3;d=2.8;box(g,0,1.4,0,3,2.8,2.8,mats.white);box(g,0,1.5,1.42,2,1,.04,new THREE.MeshStandardMaterial({color:0xd6a73d,emissive:0x47330b}));box(g,0,.6,1.5,1.2,.12,.9,mats.dark);}
   else if(key==='clean'||key==='cmp'){box(g,0,.6,0,3,1.2,1.8,mats.white);for(let x=-.8;x<=.9;x+=.8){if(key==='cmp')cylinder(g,x,1.3,0,.32,.16,mats.dark);else box(g,x,1.25,0,.6,.1,1.2,mats.dark);}box(g,0,1.9,-.6,3,1.2,.1,mats.glass);}
   else{box(g,0,.7,0,2.2,1.4,1.8,mats.white);cylinder(g,0,1.9,0,.4,1.1,mats.metal);box(g,.7,1.5,.5,.7,.65,.1,mats.dark);}
   const screen=box(g,w/2-.45,1.65,d/2+.08,.6,.45,.07,mats.dark);box(g,w/2-.45,1.65,d/2+.13,.48,.32,.02,mats.cyan);
   const light=cylinder(g,w/2-.2,2.9,0,.09,.24,mats.cyan.clone());machineObjects[key]={group:g,light,screen};colliders.push({x:t.x,z:t.z,w:w/2+.3,d:d/2+.3});label(t.id+' / '+t.name.toUpperCase(),t.x,3.5,t.z);
 }
 const player=new THREE.Group();scene.add(player);box(player,0,.9,0,.43,.7,.28,mats.white);cylinder(player,0,1.48,0,.22,.4,mats.white);box(player,0,1.5,-.18,.26,.12,.05,mats.glass);
 const limbs=[];for(const x of [-.15,.15]){limbs.push(box(player,x,.35,0,.17,.6,.19,mats.white));}for(const x of [-.32,.32])limbs.push(box(player,x,.88,0,.15,.6,.17,mats.white));
 let pos=new THREE.Vector3(0,0,9.3),yaw=0,pitch=.12,third=true,paused=false,last=performance.now(),walk=0;
 const keys=new Set();let drag=null;let nearest='gown';
 function resize(){const w=container.clientWidth,h=container.clientHeight;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();}new ResizeObserver(resize).observe(container);resize();
 function keydown(e){if(paused||['INPUT','SELECT','TEXTAREA'].includes(e.target.tagName)||document.querySelector('dialog[open]'))return;if(['ArrowUp','ArrowDown','ArrowLeft','ArrowRight',' '].includes(e.key))e.preventDefault();keys.add(e.key.toLowerCase());if(e.key.toLowerCase()==='e'&&nearest)onInteract(nearest);if(e.key.toLowerCase()==='v')third=!third;}
 window.addEventListener('keydown',keydown);window.addEventListener('keyup',e=>keys.delete(e.key.toLowerCase()));window.addEventListener('blur',()=>keys.clear());
 renderer.domElement.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY};renderer.domElement.setPointerCapture(e.pointerId);});
 renderer.domElement.addEventListener('pointermove',e=>{if(!drag||paused)return;yaw-=(e.clientX-drag.x)*.006;pitch=Math.max(-.4,Math.min(.7,pitch+(e.clientY-drag.y)*.004));drag={x:e.clientX,y:e.clientY};});
 renderer.domElement.addEventListener('pointerup',()=>drag=null);renderer.domElement.addEventListener('pointercancel',()=>drag=null);
 const moveMap={forward:'w',back:'s',left:'a',right:'d'};
 function frame(now){requestAnimationFrame(frame);const dt=Math.min((now-last)/1000,.05);last=now;const modal=document.querySelector('dialog[open]');
  if(!paused&&!modal){let dx=(keys.has('d')||keys.has('arrowright')?1:0)-(keys.has('a')||keys.has('arrowleft')?1:0),dz=(keys.has('s')||keys.has('arrowdown')?1:0)-(keys.has('w')||keys.has('arrowup')?1:0);const len=Math.hypot(dx,dz)||1;dx/=len;dz/=len;const mx=(dx*Math.cos(yaw)+dz*Math.sin(yaw))*dt*3.2,mz=(-dx*Math.sin(yaw)+dz*Math.cos(yaw))*dt*3.2;
   const safe=(x,z)=>Math.abs(x)<13.7&&z>-13.7&&z<13.7&&!colliders.some(c=>Math.abs(x-c.x)<c.w&&Math.abs(z-c.z)<c.d);
   if(safe(pos.x+mx,pos.z))pos.x+=mx;if(safe(pos.x,pos.z+mz))pos.z+=mz;if(dx||dz)walk+=dt*9;else walk=0;
  }
  player.position.copy(pos);player.rotation.y=yaw;player.visible=third;limbs.forEach((l,i)=>l.rotation.x=Math.sin(walk)*(i%2?-.3:.3));
  const eye=pos.clone().add(new THREE.Vector3(0,1.6,0));const forward=new THREE.Vector3(-Math.sin(yaw),-pitch,-Math.cos(yaw));
  camera.position.copy(third?eye.clone().add(new THREE.Vector3(Math.sin(yaw)*4.5,2.2,Math.cos(yaw)*4.5)):eye);camera.lookAt(eye.clone().add(forward.multiplyScalar(third?2:8)));
  let distance=3.8;nearest=null;for(const[k,t]of Object.entries(tools)){const dist=Math.hypot(pos.x-t.x,pos.z-t.z);if(dist<distance){distance=dist;nearest=k;}}
  oht.position.x=Math.sin(now*.0002)*8;renderer.render(scene,camera);
 }
 requestAnimationFrame(frame);
 return {interact(){if(nearest)onInteract(nearest);return nearest;},camera(){third=!third;return third;},pause(value){paused=value;keys.clear();},move(direction,down){if(down)keys.add(moveMap[direction]);else keys.delete(moveMap[direction]);},setProfile(p){rail.visible=p.diameter===300;},update(state){for(const[k,obj]of Object.entries(machineObjects)){const t=state.tools[k];obj.light.material.color.set(t.state==='FAULT'?0xff5555:t.state==='RUNNING'?0xffbb44:0x3ccfb5);obj.light.material.emissive.copy(obj.light.material.color).multiplyScalar(.3);}},focus(key){const t=tools[key];pos.set(t.x,0,Math.min(13.6,t.z+2.8));yaw=0;}};
}
