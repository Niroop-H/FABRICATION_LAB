// Supports the preview service's --host/--port/--strictPort arguments.
import {spawn} from 'node:child_process';
const args=process.argv.slice(2);
function option(name,fallback){const index=args.lastIndexOf(name);return index<0?fallback:args[index+1];}
const child=spawn(process.env.CODEX_PRIMARY_RUNTIME_PYTHON||'python',['-m','flask','--app','app','run','--host',option('--host','127.0.0.1'),'--port',option('--port','3000')],{stdio:'inherit'});
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>child.kill(signal));
child.on('exit',code=>process.exit(code??0));
