# Construct for developers

Construct is a small, standard-library Python toolkit with a declarative scene contract, a command line, an MCP server
and skills for Claude Code and Hermes. Build it into an agent, a pipeline or an app.

## What you get

- **A scene contract** ([CONTRACT.md](../../CONTRACT.md)): a scene is data, never code. It says what the thing is
  (facts, parts, how they assemble and open, how each is known), and Construct decides how it looks.
- **A check that repairs:** every problem comes back with its JSON path and a fix hint, so an agent repairs the scene
  until it is clean (`construct check --json`). `--fit` adds how its solids meet.
- **One output page** with no dependencies, plus exports (glTF, OBJ, STL, 3MF, FCStd, STEP), review stills, a critic
  packet and an improvement loop with an independent critic.
- **Any model:** the MCP server, the Claude Code and Hermes skills, or `construct author` with any OpenAI-compatible
  endpoint.

## Try it

```sh
git clone https://github.com/rtmandreyev/construct.git && cd construct
python3 construct_hologram/cli.py params book --variant paperback --output book.json
python3 construct_hologram/cli.py check book.json --json
python3 construct_hologram/cli.py build book.json --out out
```

As an MCP server:

```json
{"mcpServers": {"construct": {"command": "python3", "args": ["/path/to/construct/construct_hologram/server.py"]}}}
```

## Go deeper

- [Using Construct](../USING.md): every way to run it
- [Development](../DEVELOPMENT.md): the code, the tests, and building Construct into your own tools
- [Evaluation](../EVALUATION.md): how models compare, and how to score your own
- [The scene contract](../../CONTRACT.md)
