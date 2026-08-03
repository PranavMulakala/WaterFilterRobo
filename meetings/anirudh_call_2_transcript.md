# Anirudh call #2 — 2026-08-02

**Source:** `~/Documents/Zoom/2026-08-02 20.29.40 Ani/video1385395956.mp4` (32 min 37 s).
Machine transcript, faster-whisper `medium`. **No speaker diarization** — the body below is
unlabelled; every attribution in this summary was checked against surrounding turns.

> **Attribution warning.** The most valuable thing on this call and the easiest thing to get
> wrong is *who said what*. Pranav asks the questions and is the source of every claim about
> DrinkPrime's business; Anirudh answers and is the source of the robotics advice. Several
> points below look like advisor guidance and are not. They are marked.

---

## Key advice — Anirudh **[verbal]**

- **Stay on MuJoCo for now.** For the simple objects at the start, the simulator "doesn't really
  matter." NVIDIA (Isaac) is "the most cutting edge" for complex assets — he named cables — and
  is what to move to *when you get there*, not before. `[00:19]–[00:41]`
- **A script is not a policy, and that's the real limit of the demo.** A hard-coded sequence only
  produces useful actions because every object sits in a known position; move them and "those
  actions won't be useful anymore... cause you hard coded them" — which is exactly where you have
  to train models. Grounded in Proprio's own case: their robot drives up to a rack and "it's not
  going to be the exact same position." He was explicit that scripting is *fine at this stage*
  ("this is like cool for like demo purposes"). `[12:05]–[13:59]`
- **A simulation demo has limited persuasive value.** Its purpose is your own understanding before
  spending on hardware. "Not many people will look at this and be like, oh, this is cool cause
  it's in simulation. Like people want to see robots in the real world... investors and shit."
  He qualified the demo's persuasive value — he did **not** say it's worthless, and he said
  nothing about the DrinkPrime founder specifically. `[18:32]–[19:17]`
- **A failure seen in simulation is not automatically a real failure.** Drops and lost friction
  are *sometimes* just a bad simulator — up to outright bugs where the gripper passes through the
  object. Hedged ("sometimes... it might just be"), not a general claim. `[18:10]–[18:32]`
- **Before choosing any vision approach, ask DrinkPrime how their own workers grade a cartridge.**
  Do they inspect visually? Is there a wear indicator, a colour change? Or is it the *feel*?
  "There's no like a single classifier that will do this for you." If the wear is clearly visual,
  an off-the-shelf VLM or GPT may be enough; a custom model is a later problem. `[21:02]–[21:46]`
- **Ask for the STL/STEP file — now.** Fastest route to real geometry: "just literally ask him for
  like the STL file or the step file... which I assume they have because they're the ones who make
  the components." It can be asked for immediately because "they don't really need the real object
  for that." Getting it into sim is something Claude "can probably do once you have the file."
  `[22:27]–[23:10]`
- **Proprio went real-first, not sim-first.** "Not for like what we're doing at the company...
  we do everything in real" — they got a robot, collected data with it in the real world, teleoped
  it themselves rather than outsourcing, and "didn't need like too much data." Read his
  "start in simulation" advice as guidance for a team *learning the space*, not as how his own
  company operates. (Same turn also contains a contradictory "We had some sim" — garbled.)
  `[06:23]–[07:04]`
- **The learned-policy iteration loop is ~7 hours.** Collect, train, discover the policy repeats
  the same mistake, re-collect — "you have to wait like another seven hours." Two or three
  policies a day. "You can't really get around that." No model, GPU or dataset size attached.
  `[27:06]–[27:30]`
- **Don't buy monitoring tooling yet.** Proprio watches runs in person and marks success by hand.
  He's heard of YC companies doing camera-based automatic evaluation but "I don't know how good
  they are." "When you're starting, it doesn't make too much sense to pay a lot of money for that
  kind of stuff." `[24:36]–[25:48]`
- **90%+ is achievable in your own environment** on *some* tasks; the hard part is someone else's
  environment, where "everything looks a little bit different." This is a real-robot learned-policy
  figure, not a simulation score — not a yardstick for our MuJoCo numbers. `[24:11]`
- **The robotics-devtools idea is "a good idea" on a high level, but unfocused.** Companies already
  do the pieces — automatic evaluation, automatic data annotation. "You just have to figure out
  specifically what you're going to do first." `[29:06]–[30:00]`
- Learn the *concepts*; Claude will do the coding. `[30:48]–[31:12]`
- **OpenPI (Physical Intelligence) re-confirmed** as the model he'd recommended; he'll text the
  link. `[02:07]`
- Proprio has **deprioritised decommissioning** — smaller market, "they don't have too much
  money." `[19:54]–[20:17]`

## Claims that are **Pranav's, not Anirudh's** — do not file as advice

- **Throughput, not labour cost, is the founder's constraint.** "He can find people and he's not
  paying them too much. But the issue is that he thinks it's not as fast." This is Pranav relaying
  the founder, secondhand and unconfirmed. Anirudh's only contribution was the read-back "So your
  robots would have to be faster than a human," which Pranav ratified with "Pretty much." Real and
  important — but it is **not** an advisor reframe. `[04:42]–[05:28]`
- **The labour figure is unusable.** "It's 10K per... two workers, two shifts, *hypothetically*"
  then "10K wise total together... USD wise for each worker." Total-together and for-each-worker
  cannot both hold, no time unit is ever given, and Pranav labels it hypothetical himself. **Do not
  record it, and do not reconcile it against the existing $1.50–2.50/hr line** without asking him.
  `[04:42]–[05:04]`
- **Market size is his own Perplexity research**, unsourced: India ~$2.7 B today, "7.5" in about
  four years — *the unit is never spoken*. Anirudh's only response was "yeah, I guess it makes
  sense." Not from the founder, not from the advisor. `[31:37]–[31:50]`
- **He described the cell to Anirudh as fully static** — "all like the pieces are just static"
  `[12:29]`. The repo says otherwise (randomised spawn ±40 mm / 360° yaw, 125 randomised trials).
  Anirudh's script-vs-policy advice was therefore given on an understated picture of what we built.

## Decisions

1. Stay on MuJoCo; revisit NVIDIA/Isaac only if the task grows to complex deformables.
2. The scripted controller is acceptable for the demo stage — the limitation is generalisation.
3. Hardware remains unbought; nothing on this call changed that.

## Action items

| # | Item | Owner | Notes |
|---|---|---|---|
| 1 | Ask DrinkPrime for the cartridge **STL/STEP file** | Pranav | Do now — independent of the device shipment |
| 2 | Ask **how DrinkPrime's workers grade a cartridge** (visual cue? colour? feel?) | Pranav | Gates the whole inspection approach |
| 3 | Text the OpenPI link | Anirudh | `[02:07]` |
| 4 | Receive tech docs for the full refurb process | DrinkPrime contact | Expected 2026-08-03, after he talks to their technical executives `[02:41]` |
| 5 | Diagnose the v4 end-to-end gap (routes ~100%, end-to-end ~87%) | Pranav | His words: "I don't know what broke. So I got to go back and look into it" `[01:05]` |
| 6 | **Confirm which video goes to the founder** | Pranav | On the call he could not tell which clip was on screen — see caveat below |

## Bearing on `CLAUDE.md`'s backlog

- **Backlog 2 (real geometry, "when the refurb video + device arrive")** — partly actionable now.
  The CAD file is a separate, faster ask than the physical unit. Item stays blocked, but the
  blocker moves from *waiting on a shipment* to *making an ask nobody has made yet*.
- **Backlog 0a (inspection)** — before more vision work, get the customer's own grading criteria.
  If wear is visually obvious, an off-the-shelf VLM may beat the hand-tuned HSV classifier; if
  workers grade by *feel*, camera-only inspection is the wrong architecture.
- **New verification item** — confirm what is actually randomised vs fixed, and correct the
  description given on the call.
- **Known-gotchas caveat** — the cap-grip drop is recorded as a design input for DrinkPrime.
  Anirudh's warning that sim drops are *sometimes* artifacts doesn't overturn it, but it belongs
  next to it. He did **not** question the 16–18 % untwist slip; he read it back approvingly.

---

## Transcription notes

- `faster-whisper 1.2.1`, model **`medium`**, `int8` on CPU, `language=en`, `beam_size=5`, VAD
  filter on. 559 segments. A `small`-model pass was also run and kept for cross-checking.
- **No diarization.** Speaker attributions exist only in this summary, not in the body.
- Known project vocabulary was corrected after transcription — MuJoCo, NVIDIA, OpenPI, VLM,
  Claude, teleop, cartridge, Perplexity, wrist cam, STL/STEP. Both passes rendered "VLM" as "BLM"
  and mangled "MuJoCo" throughout; those are ASR errors, not speech.
- **Do not quote the `[09:17]` line.** The two model passes disagree on its polarity — `medium`
  reads "I don't think this is a failed run", `small` reads "I think this is the failed run."
  Treat `08:52–09:20` as unreliable; it sits inside a 25 s segment spanning ~19 s of silence while
  a video was being scrubbed.
- `[31:50]` is also garbled ("it's going to explain. Billion.") — a ~3.5 s dropout where the
  `small` pass hears an interjected "Billion? / Billion." exchange.
- Audio-only stretch `[16:56]–[18:10]` is a gap where a link was being shared.

---

# Transcript

**[00:00]** is enough for it. MuJoCo was not bad as well. That's good. Okay. Okay. Not bad. Do you think for us, we would honestly have to look at the, like we got Isaac, the NVIDIA thing you just mentioned? No, like when you're talking to, I think the main purpose of this is just to like

**[00:19]** proof of concept to show that you guys can like build something. I think like for some of the more like complicated assets like cables and stuff like that, it's going to be really hard to simulate. But I think Nvidia is like probably the most cutting edge in terms of simulating those like more complex objects. So when you get to that, you want to start like using the other thing about that. I think for simple stuff that you're starting off with,

**[00:41]** doesn't really matter. You can use MuJoCo. Okay. Okay. That's good. So basically the video, I can tend to later, but it just pulls a filter cartridge out of the used unit. And it looks at it with a camera and it decides like whether it's clean enough to reinstall it or bin it or fit a new one. And I think it's actually pixelated. So everything's actually like looking at it. And then all the three routes,

**[01:05]** like they pretty much add it, like they're a hundred percent. Only the end to end is like 87%. And I think it's like the gap is like the classifier is wrong, but I'm not gonna lie, I don't know what broke. So I got to go back and look into it. But- Wait, hold up. So you have like the, you have like the entire thing in simulation right now? Yeah. Oh shit. You have like the, like how did you get the cartridge and all that stuff

**[01:28]** in the sim? Like you have, how did you like- Oh, I use the image classification. Oh, so are you like, is the simulation thing like it's like, like the physical object is- Oh no, no. Fuck no, fuck no, no. It's just, no, no, no. We're getting all the specific parts being shipped out to us and the tech docs for like the actual process of the thing is going to be sent to us in tomorrow. Like he's going to send it. Fuck

**[01:49]** I cannot do that shit in a day, bro. Yeah. But, but yeah, no, I was looking into that. And then I know you mentioned something yesterday about an open source model that sorts the L. I forgot what you mentioned yesterday. No, that was, I think it was,

**[02:07]** I'll just text it to you. OpenPI physical intelligence. And then they have- Yeah. OpenPI I think is what I was talking about. There's like some other thing, right? The robot? No, no, no, not the robot. That's just, I don't know what that is, but

**[02:28]** no, I'll come back to that. It's not that deep, but okay. Anyway, blah, blah, that's pretty much done. Right. And then I think one of it is, I have a question on this.

**[02:41]** So it's all about, so I think the biggest problem right now, the demo is like limits wise, right? It's like, it's all SIM. There's no hardware. So like seeing it, it's just like, it's all like simulation, right? I don't really know like what's going to happen or not. So I think tomorrow when we get like the, their technical documents, cause he's going to talk to his, their like chief executive technical people and like get the documents for us, like for the entire process. I guess the question that I had for you is for the

**[03:06]** staging nest and like the regroup part of it, is that like what like a real like arm would do, for example, something that maybe like you guys would do is a situation that would happen to it. Is it like a, is it like a trick that I'm kind of like missing this part? What was it? So I heard the second, what was the actual question? So is that, so when, when an arm gets put into production, right? For any, any other purpose,

**[03:28]** the, the re-gripping part, like the staging nest and the re-gripping part, like, you know, like when something like it falls or it's like a, it's like a, it's like a issue where it's like, like something where like you're trying to grip the piece apart and it's like not gripping properly, right? Does this actually happen in like real life? Is there like some, is there a way to like, like fix this kind of, is what I'm asking?

**[03:51]** Wait, so can you, so is this like, okay, so is this like a failure thing that you're seeing in the simulation thing right now? Okay, so it's like, what is it trying to pick up? Um, the cartridge. Okay, wait, so you did get the cartridge into the simulation environment then? Oh, I did. You're like... But it's not like the actual cartridge that's like we're going to be used, but it's just like a fake cartridge. Oh, okay. Okay. So it's, so it's picking it up and then what's happening. So like, it's just the, you know,

**[04:18]** yeah, I think it'll be easier. Oh, that's fucking this bitch, bro. Hold on. Nice. Fuck, I'm recording. I realized.

**[04:42]** Also, um, I was looking at the market was, bro, I'm not like, there's no competition at all. I was in Perplexity research and like, I was just doing research too. There's like, not competition wise, but it's like, no, I'm like really doing it, focusing on why. And then as you said, right, I was like wondering why, right? I think the biggest main point is it's like workers wise, it's 10K per, um, like they get like two workers, two shifts, hypothetically, right? We're talking.

**[05:04]** They get paid, um, 10K wise total together, um, USD wise for each worker. But I think that the throughput, like the output of, uh, what's being produced, it's not like equivalent to like what the guy wants. And he's, he's expanding to a hundred cities and he's already based in like a bunch of cities right now. So sure. So, so for him, it's not so in India, like there's just definitely labor, like he can find people and he's not paying them too much. But the issue is that he thinks

**[05:28]** it's not as fast. So your robots would have to be faster than a human. Pretty much. Okay. Okay. Let me see in the videos too. Uh, just check your messages. I guess I can send it there. Yeah. It doesn't take a minute to load, but yeah, you're good. I'm going to send you the latest one. Uh, let's say the one I,

**[05:50]** yo, how the fuck did I get a bitch? Oh, I'm so retarded, bro. You guys right now, bro. Yo,

**[06:23]** yo, tell me, tell me, is it, is it actually produced to MP4, right? No, I haven't. No, no, no. Did you guys, you guys have never did Sims for your, for your thing at all? Um, not for like what we're doing at the company. We haven't done sim. We had some sim. Or y'all use like your own like starting like you, you made like a small,

**[06:44]** like, I don't know how you guys started. Like what do you guys do initially? Uh, to like trade stuff. Yeah, we do everything in real. So like we had got our robot. We collected data, like with the robot and like in the real world. We just faint on that. You did teleop? I forgot. Yeah. Yeah, we did teleop. India? No, we just, we just did it ourselves.

**[07:04]** Yeah. We didn't need like too much data. Okay. Okay. Okay. Here's the full thing sending. Okay. But no, it's taking a minute, but wait, you want to show your screen if it's on your laptop? Uh, yeah, let me have a screen. Maybe faster to my like lap is bugging as

**[07:28]** far as so tell me if I'm lagging, but you're not lagging. I just can't see your screen. Oh, okay. Uh, you see it. Yeah. That was tough. But, um, okay. So this is what I'm talking about, right? So this is the old corner in this case, and this is the wrist

**[07:52]** cam video on the bottom, right? So like, I mean, we're going to fucking use teleop, probably the motherfuckers, but, um, yeah. So my problem is like at a certain point, right? Like where it was, maybe I think it's towards the end, but where the fuck is it?

**[08:19]** But like, do you see like here when, when like you're inserting it, yeah, it needs to be a certain angle, certain position. Like I'm assuming it needs to be a certain, like you said, like it needs to like turn into a place where you know, you had a torque on it. Yeah. But the problem is like, you see how it's wobbling and stuff and like it's losing its grip. It's not supposed to drop it that fast, right? So, and it picks it up, it tries to readjust it and it's not, it's,

**[08:43]** it's not right. And then he tries to do it again. Wait, am I fucking, is this the right

**[08:52]** video, bro? Hold on. You know what? I think, I think this is a, this is a fully entire

**[09:17]** run where it ran a hundred percent. I don't think this is a failed run, but like, well, I'm kind of saying it's like one of the runs is like it failed where like it's, it basically like, so you see the gripping part. Yeah. Like it failed where the point like it's like, it's dropping it early through here and like it's not in the position, right? So it keeps like how to replace it, replace it, replace it. Yeah. So,

**[09:39]** my question is, yeah, yeah, go ahead. So first, like, how is this working? Like, is this like, you train some, a model to do it or is it like, is this group

**[09:48]** that's like scripting arms? Do you know? So I think basically,

**[10:19]** this is the fourth version, right? Okay. But I think the whole thing is with MuJoCo and it's like, it's one file. There's like four different versions. And I think it's,

**[10:30]** it's a script, it's a script. So like every, it's like, it basically kind of learns

**[10:49]** by itself. So I think it's a script that learns, like it keeps like fixing and adjusting every single time. So it keeps going to different versions. Oh, I see. But then what's, what's making the updates? Like, like, for example, like let's say it messes up somehow. Yeah. Like the next time, like, how does it know how to like fix itself? Like, is it like,

**[11:09]** yeah, like, are you like training a model or is it like, Claude is like looking at it and saying like, okay, I sent, I made it do this last time. So basically, yeah, no, no, no, sure. I mean, so I think Claude, when it, so for like, I go to four different phases, right? So the first phase is actually doing it. And then phase B is actually trying to find out what the marginal error is. So for example, like, oh, just moved by a couple

**[11:31]** of milliliters off, right? And then Claude notices it in phase C. Phase C, it creates the staging-ness where like, it tries to find out like what exactly it messed up on and does the best to correct that. Okay. So for example, like, let's say, like, I don't know, like it's like taking the filter out and it's like putting the filter in, like the white thing on the rightmost side of the screen. Yeah. That's what it's like trying to put it into, right? Yeah. But let's say for example,

**[11:55]** like that was like moved to like one foot, like down or something. Yeah. Would it like not work anymore? Or would it like be able to like visually look at it and like update?

**[12:05]** Okay. Okay. So, okay. Then if it's like a script, it sounds like what's happening is that like the position of each of these things is like static, like the, I don't know, like the water, the filter, everything is like supposed to be like a predetermined position. Yeah. And it's like, like, I don't know exactly how it works, which is like, so I can't like super tell you how to like fix it. No, no, no. This is the hypothetical. We don't even know like the actual, like how they do it. Right. So we're,

**[12:29]** I'll go more tomorrow. This is just, but this is all just static stuff. Like all like the pieces are just static. Okay. So this is just like for like demo purposes, basically. I'm only talking about like how like in real life, like how would you like, like for example, you write like, let's just say like one of your pieces, let's just say, do you also do refurbishment stuff? I'm assuming for,

**[12:51]** not refurbishment directly, but some of the stuff I would say is like somewhat related, like similar sort of tasks. That type of stuff. Right. So let's just say there's a, there's a use case where like, is, is, is your stuff, I mean, I guess your stuff is static, right? Cause I feel like it's like hardware thing is not going to move anywhere, but like, do you have any use cases or like situations where like, it's not going to static, I guess, like do you guys account for that? Well, like the thing is like, for example, like,

**[13:14]** like if you're in a data center, our robot needs to move around. Yeah. Which means I like, you know, let's say like drives up to like a rack. Yeah. One time it's, and it drives up to it like another time. It's not going to be the exact same position, right? There will be like some variation. Like it's not going to be able to get the same exact spot. That's why you have to like, kind of like do it dynamically. You can't just like script the arm. So when I say script, I mean like you can literally just like hard code a set of like actions and send

**[13:38]** it to the arm. And because like every, all the objects are in the same spot, those actions are going to do something useful because you know where everything is. But like, let's say some of the objects moved, then those actions won't be useful anymore. Right. Cause you hard coded them. That's what I mean when I say a script. That kind of makes sense. So I think like if this is a script, then like, then like for demo purposes, it's, it's like fine.

**[13:59]** But yeah, like for like, I think you had to kind of count like the wrist height, for example, like of like how far it is from like the thing. And like, you got to take a bunch of other things. Exactly. And for like that kind of stuff where like, you don't know, for example, you don't know exactly where things are going to be and you can't just script them and like hard code them beforehand. That's kind of where you have to like train models. And that's kind of where like the whole like AI part comes into robotics.

**[14:24]** Yeah. I think, yeah, I know what you mean. I think also like what I did is like everything it's like, I know everything in Claude, like it creates a baseline that I keep track of and it uses that to like evaluate for like the next run, obviously on the failure. So there's like a certain baseline for everything and it keeps on improving on that. I think on the cleaning part of it, it did mess up sometimes. So I guess we got to fix that, but yeah. Okay. I know what you mean. And I know there's, I know views are important too,

**[14:48]** right? Part of it, part of simulation event, like, like, but you can have like a single view or like a double view. Yeah. So usually like you'll have like one like overhead or like scene camera, which could be something like this, where you can kind of see like everything. Yeah. And then like something that's also important is like having a wrist camera like you have in the bottom, right? Yeah. That's important because like it'll allow you to see like more like fine grain details that you're going to miss from like a camera that's like

**[15:13]** further away. So like wrist camera is like super popular. And then usually like you have like an overhead camera or something like this. Oh, okay. You know what? I'm actually looking at my notes, bro. So it says every phase has a completion condition and a timeout and the timeout trigger recovery is rather than failure. The one architectural decision

**[15:34]** that mattered is every gate judges the work piece, not the tool. So whether the insertion is finished and decided where the cartridge is and how upright it is, not by where the wrist is, that sounds obvious that it isn't the original code and a jammed parts to let the wrist descend past it. So a jams reported success and got two phases later, same principle. Okay. I think,

**[15:55]** oh, for the failure wise. So basically I think when like jams happen, I guess, it's caught like in the phases later where it tries to retry that there are retry paths. And then for like same principle to like fix the untwist ones, like untwisted ones, you had to close the loop on the cartridge angle because the cap, like it loses grip.

**[16:18]** And I probably lose a grip 16 to 18% of the rotation on slip. I don't know what that means, but. Go ahead. Yeah. I mean, if so it looks like it's saying that the gripper itself is losing like friction with the object. Yeah. Yeah. I mean like, okay. But I think that's, can you share the Claude thing that you're, I don't know if

**[16:42]** you can share that as well. And I can also just see what it's saying. Here's your question.

**[16:56]** Uh, I can see the video still. Oh, there we go. Yeah. I saw your text. Okay. Yeah. Um,

**[18:10]** one thing I will say is usually like, like sometimes like shit will just like drop in simulation or like we'll lose like friction, but sometimes it's only just cause it's, it might just because the simulation is not good. Like for example, sometimes it'll just drop things to it and like real life it will drop because there's enough friction. Oh, okay. So it's just like a, it's just like a variable that's like displayed. Yeah. Sometimes simulation just isn't good. Like sometimes there's like literally just like bugs where like it'll go

**[18:32]** through like the object because of like an issue in the simulation environment and then it'll like drop something. But obviously in the real world, you're not going to have that. You think, you think simulation is a good, we need, you think for simulation POC wise, like it's something that we should do beforehand or like you think we should get straight into it. Like I think simulations like useful like to actually like learn stuff

**[18:54]** yourself before you invest a lot in hardware. Yeah. So like, this is like cool for like demo purposes, but you want to make sure that you kind of understand like how it's working and what's going on. And the main purpose of that is like not like don't really like honestly like not many people will look at this and be like, Oh, this is cool. Cause it's in simulation. Like people want to see robots in the real world. Like that's what people will think it's cool. Like investors and shit. So I mean, this is mainly just like, so you

**[19:17]** have an understanding of like how to like generally approach the problem. And then when you get hardware, you can hopefully apply some of the same, like, I don't know, skills and stuff to like real hardware. Okay. Okay. Cool. Oh yeah. That's the only question I have for the coding wise, but yeah, let me talk about some other stuff.

**[19:54]** Okay. I know you also do something called for the decommissioning. You have a decommissioning line, right? Um, yeah, that was one of the things we were looking at. Not so much anymore, but like one of the, basically the idea was like, you have servers, you just take out parts of the server, stuff like that. Okay. Is this mean you guys are just looking at or not already? Um, not too much anymore. I think like the market is just like much less for decommissioning. Like a lot of these like people who like do decommissioning,

**[20:17]** they don't have too much money. So they can't really pay for like robots like that. Okay. Um, okay. So another question I had is for like, it's like in terms of vision. So for the, like the condition, like when you're expecting the condition of the cartridge, um, what we're doing is using like rendered frames, I think. So it's like, um, like coverage of the entire thing plus like the texture, uh, that's like calibrating when

**[20:40]** frozen. So I think for like the actual arm and like, if it's deployed, for example, right would, uh, um, would like a classic, it says here, like, uh, we should maybe use a VLM grading photos or is there like a different trainer, a classifier that you think we should use? But it said VLM, but I'm not sure if it's like, um, to like, you said to create the

**[21:02]** quality of the cartridge, right? Yeah. Yeah. I mean, I think the first thing is like, you're going to have to like probably ask the person that you're working with, like how do their workers determine like the quality of the cartridge? Cause it's going to be the same thing. Like do the workers like just manually inspect it? And do they look for some sort of like visual cues? Like for example, like is the cartridge like, if it's worn out, is some indicator on the cartridge, like does it change color? Cause

**[21:23]** sometimes, I don't know, filters will have that sort of stuff. Um, or is it like, you know, the feel of something is different. Um, there's no like, there's no like one, there's no like a single classifier that will do this for you, but like a VLM is like mostly useful if it's like a visual thing and you can clearly see like this cartridge is like clearly like fucked up and old, um, because of this feature. And then maybe you'll get away with using like an off the shelf, like VLM or like

**[21:46]** actually like GPT or something. Um, I can just like look at it and then just literally tell you whether it's like worn out or not. Um, but if you want something more accurate, you'll probably have to like train a custom model, but that's like in the future. I feel like you can probably get away with just using. Yeah.

**[22:02]** Okay. And then when the actual, when, when, when the dude sends the actual parts to us, what's like the fastest like way of like we can actually like get that exact like, um, scan of that, like did it mention and everything into like, um, I guess something like maybe like CAD, I guess. I don't know what we use, what you guys like, what we, what you use for SIM, but like how would you, you don't want the faster way to get like an actual good replica of it into SIM is like with the actual dimensions and everything.

**[22:27]** Yeah. I mean, fastest way would be to just literally ask him for like the STL file or the step file. Um, which is basically like there are 3d files that allow you to like put stuff in a CAD. Um, and then from there, I feel like you could probably ask Claude to take like an existing STL file or step file, which I assume they have because they're the ones who make the components, right? Yeah. Um, yeah. So if they manufacture, it's like super likely that they'll have, and this is stuff you could ask for

**[22:50]** like right now. Um, it's like super hard to like take an object and then replicate it using the physical object, but it's much easier if they have some sort of like, I don't know, like diagram with it in like on a computer already that you can just take as a file. It's like a data source. Um, so like that you can just look, ask him for right now, cause they don't really need the real object for that.

**[23:10]** But yeah, but then still like getting into simulation is going to be like, I think, I think that's something that Claude can probably do once you have the file. Okay. Yeah. Okay. Um, okay. And I guess this is more of like the, uh, just like, I'm wondering how your thing works. So like, what would you like, what, like, how does, I, how does the teleop session like, like look like for you guys, um,

**[23:32]** for like, like demos, like actually like deploying like a policy for example. So like, like, do you guys like, uh, do you guys own everything like, uh, like scripts, uh, and all that stuff, like, or how do you decide like when something is ready or like a policy is ready?

**[23:48]** Yeah. I mean, I think we're like, kind of far from like actually deploying in like an actual environment and saying like, actually work. Yeah. I like, I think like most robotics companies are pretty far. Honestly, they just kind of like post and like try to get themselves high, but they're like years away from like getting the shit to work. I mean, um, yeah, I mean, you can like train, like collect some data, train a policy and you can evaluate it. Like you can say like, you know, how accurate is it?

**[24:11]** How like out of 10 times, how many times will it just do it successfully? And that like in your own environment, you can like get to a pretty high accuracy. Like you can get to like 90 plus accuracy on some of these tasks. Um, I think the difficulties like when you go into someone else's environment and then try to do the same task there, um, then everything looks a little bit different. So it's maybe a little bit harder. Um, but yeah, I feel like SIM is a good starting point. It's like easier to evaluate in simulation as well.

**[24:36]** Okay. And then when, when like something runs, like let's say you're doing a demo, like, I don't know how you guys do it, but like when something runs at times, right? Like once you're like arms are just running right now, how do you guys like monitor it? Like how do you like, um, is there like an alert if you guys like, it's like the success rate drops or something is missing or anything? No, I mean, usually like when the arm is like going, we're like usually like right there. Um, so like if, if it's successful, like we can literally just say like, okay,

**[25:00]** this one was a success and we like market manually as a success. Um, yeah, I mean, like usually like for the rub, you kind of have to be there most of the time, um, in case something goes wrong. Yeah. Do you know anything about like, um, about like just like checking health checks, what kind of like a health check was like, is there any like things in the industry that people do by chance? Um, what do you mean health checks? Like like automatically evaluate. Yeah, pretty much. I just see if it's like a safe

**[25:24]** and up and running. Um, there's probably some like sort of companies building something like that. Like I've heard like some companies are new, but in YC, they're making like automated evaluations where they'll have like Claude or something like just, I don't know, like if you give it a camera, it'll just like keep watching the robot and then you'll mark each thing as success or not. I don't like do automatically. Um, but I don't know how good they are or how useful it would be. Um, I

**[25:48]** feel like when you're starting, it doesn't make too much sense to like pay a lot of money for that kind of stuff. Yeah. Yeah. Okay. Okay. Um, okay. And then my next question was, let me see. Oh yeah. Um, I mean, like this is just like a question that I just had, like

**[26:12]** this is I'm trying to like soft launch an idea. So just bear with me.

**[26:17]** But, uh, do you guys like facing like issues throughout like your process of developing it? Like, was there any like, like points of like where it required manual input from you? I mean, is there like a, like I'm trying to say like, is there like a kind of like a pain point in your process of training it? Um, like for us when we're just making like one of our models, like what are the biggest pain points?

**[26:41]** Oh, like what's the most annoying like manual thing you guys had to do in your workflow? Yeah. Um, I mean, obviously collecting data is one thing, um, because we do that ourselves. So that's like obviously manual and you just have to do it. It doesn't take too long. Actually, we don't have to collect too much data. Um, yeah, but I would say like the most annoying thing is like, you know, let's say like you collect some data and your policy

**[27:06]** doesn't work. Yeah. Um, like for example, you can very clearly tell that the policy is like the model that you train is like making the same mistake over and over again. It's kind of a pan the ass because then you're like, oh shit, like maybe I should have collected data, like doing it this way instead of it's my other way. Um, and then you have to go back and then collect data, which is fine, but then you have to wait like another seven hours to like for your thing to train again. So you only really get to test it again like seven hours later.

**[27:30]** So it's like super slow, right? In a day, you can only really test like maybe two or three policies. Um, so that kind of sucks, but you can't really get around that. That's just how long it takes. Okay. Okay. Yeah. Uh, and then, okay, so well, like I was trying to ask those questions because like, um, I don't know, me and my, me and my partner were talking yesterday. Uh, oh shit. How much time do you have? Okay. We were talking yesterday and we're like, we're like, just like, we're

**[27:54]** like wondering, like, um, like we're like, we're going to like log everything we hit, like every mistake and everything we do in our journey. So, and every, I feel like every, you know, there's like, I feel like every layer in robotics has like some type of software, but like nothing to connect them. Cause I know like there's like, I guess there's three layers, right? There's like the actual data collection and I could train like the training and evaluating and actually deploying it, right? Yeah.

**[28:19]** Yeah. Right. So I know there's like, I think the yesterday you're talking about something called like, I think it was a water was it was a startup where like, yeah, water. Right. And then I think something called Robo Robo curve, they're kind of like building layer, like these like specific layers, but they're not like this is like something that doesn't really connect all them, right? Cause we were thinking like, what's like a, what's like a way where like, like everything is connected for a

**[28:42]** good software to actually like, when you're actually deploying your like your stuff to production was like, how do you manage that? You know what I mean? Yeah. Like, I don't, I don't know if you know any software exists because I was thinking and there's nothing that does exist. So if let's just say like we were to, we were to prototype me and manager and build something around this, like this, like the pain points that you just named like data, like, as I said, like,

**[29:06]** you know, like checking if, if it's up and running, checking if it's like the data collections is actually like, it's going through and everything. So like, I don't know. Yeah. Is it, you think it's a kind of garbage idea? Like what you think? No, I mean, I think it's a good idea. I think the difficulty it's like, so there's a lot of companies not doing like, they're not, I don't know, companies that are trying to like unify everything. As you mentioned, there are companies that do like automatic evaluation, which

**[29:30]** is like what, instead of me having to be there saying like, okay, this one was a success, this one was a fail, they automatically do that. That's like some level of software that helps. There's other companies that do like, they like automatically annotate your data for you, depending on what sort of task you want. Like that's another like layer, right? They're doing the data data collection side. So I don't think it's not a garbage idea, but you just have to be like a little bit more. I have to like understand the area a bit more and understand like

**[29:55]** specifically like what sort of things you need to target first.

**[30:00]** But on a high level, I think it's a good idea. You just have to like figure out specifically what you're going to do first, what things are hard for. Because I'm not really sure like what would be like the best thing to start with for that. Yeah, I know. I mean, it was just an idea we had because like we're just thinking out loud, but like you just want to buy you, but like I don't know, we're going to like try to like log everything that we hit on, like just like things, pain points that we see and kind of just like see if we can do something out of it. But I don't know, let me know like if maybe

**[30:24]** like you can be your first customer or some shit, I don't know, but like, I don't know. Yeah, I'll let you know. I think I think like right now we're like so early, like some of the everything. I mean, like you got I said you got like fucking you got so much time before you do this shit. Even us too, but we just we're just fucking starting so we'll see. But I got so much shit to fucking learn. I was trying to fucking learn the vocabulary yesterday, bro. Yeah, you're asking like we're using like Claude and shit. Yeah, I was in cloud and

**[30:48]** perplexity. Perplexity is looking better in my life in terms of research was. Yeah, but fucking learning like MuJoCo, I was trying to learn MuJoCo, like what it was and everything. And I, people said that Nvidia whatever you said, that was also good too. Yeah, I think like yeah, I would say like just like to like learn it, like learn like the concepts first, because a lot of this like specific thing like like MuJoCo,

**[31:12]** Claude, like Nvidia, like whatever you use like for the coding part, Claude can figure it out. But I think it's important that you understand like the high level like concepts. Definitely. Because that's like harder, like Claude can just like teach you that, right? You kind of have to learn it yourself. But the coding, with the coding shit it will do, so you don't have to worry too much about it. Yeah, I know. Okay. Yeah, okay. And then, do I have any other questions?

**[31:37]** No, that's it, I think. And then it was, I did market research was, it's right now in India, it's like a 2.7 billion dollar industry. It's growing pretty fast. Things are rapidly, it's going to explain. Billion.

**[31:50]** Yeah, I guess it makes sense. Yeah, it must be more important. Yeah, and it's going to expand to like 7.5 in like four years. That's what, that's what, that's what researchers say, because I think, I think water, I don't know, I think water filtration was getting more serious because it's just looking a lot lacking. What people do is a lot of water filters, because like, you know, like the high end class people, bro, like, like, I don't know if your family is Indian, like, we always use the water filter. Like it's like, it's some type of water, every household,

**[32:14]** right? So, there's definitely that part too. And also in America, it's pretty big thing. So we were thinking, actually, I didn't tell my manager this yet, but like, hold on, I don't know. Wait, it's not transcribing, but it was a fucking recording. It was a lie.

**[32:35]** All right, you know what? It doesn't matter.

