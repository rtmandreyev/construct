# Examples

Twenty-three constructs made by AI agents with Construct, each with its scene, a hero image and
how it was made. See them live, assembling, in the [examples gallery](https://rtmandreyev.github.io/construct/).

Some were made with earlier builds (Construct 0.2.0, or 0.2.1 development and release-candidate
builds). Every one was checked again with Construct 0.2.1, without changing a scene's content: all pass
`check`, and the 0.2.1 compiler builds the same construct each time, so the gallery is built
from these scenes with the release. One record was completed: the Sainte-Chapelle's round history
now includes round 15, the round its scene comes from.

| | example | model | how | made with |
|---|---|---|---|---|
| [![Sainte-Chapelle](sainte-chapelle/thumb.jpg)](sainte-chapelle/) | [Sainte-Chapelle](sainte-chapelle/) | Claude Opus | masterpiece rounds, round 15 | Construct 0.2.1 (the released rounds loop) |
| [![Toyota Land Cruiser FJ62](toyota-land-cruiser-fj62/thumb.jpg)](toyota-land-cruiser-fj62/) | [Toyota Land Cruiser FJ62](toyota-land-cruiser-fj62/) | Claude Opus | masterpiece rounds, round 11 | a Construct 0.2.1 release-candidate build (the c2p rounds variant) |
| [![Duomo di Milano](duomo-di-milano/thumb.jpg)](duomo-di-milano/) | [Duomo di Milano](duomo-di-milano/) | Claude Opus | masterpiece rounds, round 6 | a Construct 0.2.1 development build |
| [![Aston Martin DB5](aston-martin-db5/thumb.jpg)](aston-martin-db5/) | [Aston Martin DB5](aston-martin-db5/) | Claude Opus | masterpiece rounds, round 5 | a Construct 0.2.1 development build |
| [![Neuschwanstein](neuschwanstein/thumb.jpg)](neuschwanstein/) | [Neuschwanstein](neuschwanstein/) | Claude Opus | masterpiece, stopped at the 2-hour limit | a Construct 0.2.1 development build |
| [![Sagrada Família](sagrada-familia/thumb.jpg)](sagrada-familia/) | [Sagrada Família](sagrada-familia/) | GPT-6.1 Sol | masterpiece | a Construct 0.2.1 development build |
| [![Ferrari F40](ferrari-f40/thumb.jpg)](ferrari-f40/) | [Ferrari F40](ferrari-f40/) | GPT-6.1 Sol | masterpiece | a Construct 0.2.1 development build |
| [![Sydney Opera House](sydney-opera-house/thumb.jpg)](sydney-opera-house/) | [Sydney Opera House](sydney-opera-house/) | GPT-6.1 Sol | masterpiece | a Construct 0.2.1 development build |
| [![Saturn](saturn/thumb.jpg)](saturn/) | [Saturn](saturn/) | DeepSeek | masterpiece mode, through Hermes | Construct 0.2.1 |
| [![Andromeda Galaxy (M31)](andromeda-galaxy/thumb.jpg)](andromeda-galaxy/) | [Andromeda Galaxy (M31)](andromeda-galaxy/) | DeepSeek | masterpiece mode, through Hermes (last round self-reviewed) | Construct 0.2.1 |
| [![Leica M3](leica-m3/thumb.jpg)](leica-m3/) | [Leica M3](leica-m3/) | GPT-6.1 Sol | research first, standard (10 minutes) | a Construct 0.2.0 development build |
| [![Patek Philippe 5320G](patek-philippe-5320g/thumb.jpg)](patek-philippe-5320g/) | [Patek Philippe 5320G](patek-philippe-5320g/) | GPT-6.1 Sol | research first, standard (10 minutes) | a Construct 0.2.0 development build |
| [![Jackson Juggernaut ET7](jackson-juggernaut-et7/thumb.jpg)](jackson-juggernaut-et7/) | [Jackson Juggernaut ET7](jackson-juggernaut-et7/) | GPT-6.1 Sol | research first, standard (10 minutes) | a Construct 0.2.0 development build |
| [![Omega Speedmaster, calibre 321](omega-speedmaster-321/thumb.jpg)](omega-speedmaster-321/) | [Omega Speedmaster, calibre 321](omega-speedmaster-321/) | DeepSeek | research first, standard (10 minutes) | a Construct 0.2.0 development build |
| [![Revox A77](revox-a77/thumb.jpg)](revox-a77/) | [Revox A77](revox-a77/) | DeepSeek | showcase (30 minutes) | a Construct 0.2.1 development build |
| [![The Last Light: sea cliff at dusk](the-last-light/thumb.jpg)](the-last-light/) | [The Last Light: sea cliff at dusk](the-last-light/) | GPT-6.1 Sol | a single first pass | a Construct 0.2.0 development build |
| [![Brass orrery](brass-orrery/thumb.jpg)](brass-orrery/) | [Brass orrery](brass-orrery/) | GPT-6.1 Sol | a single first pass | a Construct 0.2.0 development build |
| [![Gothic cathedral nave](gothic-cathedral-nave/thumb.jpg)](gothic-cathedral-nave/) | [Gothic cathedral nave](gothic-cathedral-nave/) | GPT-6.1 Sol | a single first pass | a Construct 0.2.0 development build |
| [![Black hole](black-hole/thumb.jpg)](black-hole/) | [Black hole](black-hole/) | GPT-6.1 Sol | a single first pass | a Construct 0.2.0 development build |
| [![Tea house](tea-house/thumb.jpg)](tea-house/) | [Tea house](tea-house/) | GPT-6.1 Sol | a single first pass | a Construct 0.2.0 development build |
| [![Arturia MiniFreak](arturia-minifreak/thumb.jpg)](arturia-minifreak/) | [Arturia MiniFreak](arturia-minifreak/) | DeepSeek | a single first pass | a Construct 0.2.0 development build |
| [![Yamaha CFX](yamaha-cfx/thumb.jpg)](yamaha-cfx/) | [Yamaha CFX](yamaha-cfx/) | DeepSeek | standard (10 minutes) | Construct 0.2.0 |
| [![Porsche 911 (964)](porsche-911-964/thumb.jpg)](porsche-911-964/) | [Porsche 911 (964)](porsche-911-964/) | GPT-6.1 Sol | masterpiece | Construct 0.2.0 |

Product and place names belong to their owners. Each construct is an independent reconstruction
from public references, not an official model; the scenes cite their sources, and no reference
photograph is included here.

Build the gallery yourself: `python3 scripts/build_site.py --out site`, then serve `site/` with
any static server (see [PUBLISHING.md](../PUBLISHING.md)).
