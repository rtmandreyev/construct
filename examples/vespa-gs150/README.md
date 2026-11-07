# Vespa GS 150, an owner's scooter

[![A 1960 Vespa GS 150, a holographic construct](hero.jpg)](https://rtmandreyev.github.io/construct/examples/vespa-gs150/)

**masterpiece · GPT-6.1 Sol**

[Open the live construct](https://rtmandreyev.github.io/construct/examples/vespa-gs150/): drag to orbit, R replays the assembly, L shows labels, P shows how each part is
known, S shows it as a solid. The scene it was built from: [scene.json](scene.json); its finish for Blender and
the kit: [maps/finish.json](maps/finish.json); its kit plan: [kit-plan.json](kit-plan.json). The 1:12 kit: [in 3D](https://rtmandreyev.github.io/construct/examples/vespa-gs150/kit/assembly.html), [its booklet](https://rtmandreyev.github.io/construct/examples/vespa-gs150/kit/booklet.html) and [its plates to print](https://github.com/rtmandreyev/construct/releases/latest/download/construct-kit-vespa-gs150.zip).

A 1960 Piaggio Vespa GS 150 from two photographs of one scooter and its published specifications, in twelve
masterpiece rounds through Hermes (GPT-6.1 Sol, high reasoning), each judged by an independent critic; the run
stopped at the 12-round cap with round 12 the best. The scooter in the photos is not stock, and the construct says
so: its whitewall tyres, chrome bars, rear rack, spare wheel and legshield badges are separate parts labelled as
the owner's, not the factory's, so a restorer can tell the two apart. The side cowls lift off, the handlebar
steers and the stand folds. [Your vehicle →](../../docs/for/your-vehicle.md) ·
[A kit of your own →](../../docs/for/a-kit-of-your-own.md)

**Revised after the run.** The owner's chrome bars, rear rack, mudguard hoop and badge carrier were rebuilt as
continuous bent tubes that meet the body where they mount: they clear the floorboard, the seat and the cowls'
tails, and the badge carrier stands clear of the steering column on two arms. An independent critic then judged the
revised scene again (every score 2 of 3; the cowls' teardrop, the legshield's taper and the headlamp remain its
largest defects).

The photographs, from Wikimedia Commons, stood in for an owner's own (they are not in this repository):
[front left](https://commons.wikimedia.org/wiki/File:Vespa_GS_3_150ccm_8PS_1960_1.jpg) and
[rear right](https://commons.wikimedia.org/wiki/File:Piaggio_Vespa_150_GS_1960b.JPG), both public domain.

Build it yourself from a checkout of Construct:

```sh
python3 construct_hologram/cli.py build examples/vespa-gs150/scene.json --out out/vespa-gs150
python3 construct_hologram/cli.py export examples/vespa-gs150/scene.json --out vespa.glb --materials examples/vespa-gs150/maps/finish.json
```
