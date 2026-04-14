import { getModel, complete, registerBuiltInApiProviders } from '/Users/liangruiyuan/.openclaw/extensions/lossless-claw/node_modules/@mariozechner/pi-ai/dist/index.js';

registerBuiltInApiProviders();

const input = await new Promise((resolve, reject) => {
  let data = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', chunk => data += chunk);
  process.stdin.on('end', () => resolve(JSON.parse(data)));
  process.stdin.on('error', reject);
});

const { modelRef = 'openai-codex/gpt-5.4', systemPrompt, userPrompt } = input;

const [provider, modelId] = modelRef.split('/');
const model = getModel(provider, modelId);
const context = {
  systemPrompt,
  messages: [{ role: 'user', content: [{ type: 'text', text: userPrompt }] }]
};

const response = await complete(model, context, {
  textVerbosity: 'medium'
});

if (process.env.CODEX_DEBUG === '1') {
  console.error(JSON.stringify(response, null, 2));
}

let text = '';
for (const block of response.content || []) {
  if (block.type === 'text') text += block.text;
}
if (!text && response?.message?.content) {
  for (const block of response.message.content || []) {
    if (block.type === 'text') text += block.text;
  }
}
process.stdout.write(text);
