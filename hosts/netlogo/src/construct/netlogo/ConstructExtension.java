// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Artyom Andreyev
package construct.netlogo;

import java.awt.Desktop;
import java.awt.GraphicsEnvironment;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.nlogo.api.AnonymousCommand;
import org.nlogo.api.AnonymousReporter;
import org.nlogo.api.Argument;
import org.nlogo.api.Command;
import org.nlogo.api.Context;
import org.nlogo.api.DefaultClassManager;
import org.nlogo.api.Dump;
import org.nlogo.api.ExtensionException;
import org.nlogo.api.ExtensionManager;
import org.nlogo.api.Link;
import org.nlogo.api.Patch;
import org.nlogo.api.PrimitiveManager;
import org.nlogo.api.Reporter;
import org.nlogo.api.Turtle;
import org.nlogo.core.LogoList;
import org.nlogo.core.Syntax;
import org.nlogo.core.SyntaxJ;

/**
 * Construct for NetLogo: record a model's run, then draw it as a construct (a hologram in which height is
 * time). The recording is the same JSON Lines file construct.nls writes, so Construct's command line,
 * art direction and data lock all work with it.
 *
 *   extensions [construct]
 *   setup: ... reset-ticks  construct:start "Wolf Sheep"  construct:track-reporter "sheep" [-> count sheep]  construct:record
 *   go:    ... tick  construct:record
 *   then:  construct:draw "phase"    (writes <title>-construct/construct.html beside the model and opens it)
 *
 * With music (construct:music "track.mp3"), a tick is a moment of the track: 30 ticks a second by default.
 * construct:kick, construct:energy, construct:high and construct:hit report the music at the current tick, so
 * a model's own code can follow it, construct:run lasts the track, and the run's replay, video and 3D model
 * play in time with it.
 */
public class ConstructExtension extends DefaultClassManager {

  // ------------------------------------------------------------------ the recording's state
  static String file = null, title = "", seed = "null", patchVar = "";
  static int every = 1, patchEvery = 0, linkCount = -1;
  static double lastT = Double.NaN, lastPatchT = Double.NaN;
  static long steps = 0;   // the clock of a model that never starts the tick counter
  static boolean turtles = true, headerDone = false;
  static List<String> turtleVars = new ArrayList<>();
  static List<String> reporterNames = new ArrayList<>();
  static List<Object> reporters = new ArrayList<>();   // anonymous reporters, or the extension's own (a breed's count)
  static BufferedWriter out = null;
  static String python = System.getProperty("os.name", "").toLowerCase().contains("win") ? "python" : "python3";

  // ------------------------------------------------------------------ the music, kept across runs until construct:music ""
  static File track = null, features = null;
  static int tps = 30, musicTicks = 0;
  static String trackSha = "";
  static Map<String, double[]> music = new HashMap<>();

  @Override
  public void load(PrimitiveManager pm) {
    pm.addPrimitive("start", new Start());
    pm.addPrimitive("seed", new Seed());
    pm.addPrimitive("every", new Every());
    pm.addPrimitive("track-turtles", new TrackTurtles());
    pm.addPrimitive("track-reporter", new TrackReporter());
    pm.addPrimitive("track-patches", new TrackPatches());
    pm.addPrimitive("skip-turtles", new SkipTurtles());
    pm.addPrimitive("record", new Record());
    pm.addPrimitive("finish", new Finish());
    pm.addPrimitive("file", new FileName());
    pm.addPrimitive("draw", new Draw());
    pm.addPrimitive("set-python", new SetPython());
    pm.addPrimitive("run", new RunModel(false));
    pm.addPrimitive("run-for", new RunModel(true));
    pm.addPrimitive("music", new Music());
    pm.addPrimitive("kick", new MusicAt("kick"));
    pm.addPrimitive("energy", new MusicAt("energy"));
    pm.addPrimitive("high", new MusicAt("high"));
    pm.addPrimitive("hit", new MusicAt("onset"));
    pm.addPrimitive("music-time", new MusicTime());
    pm.addPrimitive("play", new Play());
    pm.addPrimitive("sync", new Sync());
    pm.addPrimitive("stop-music", new StopMusic());
  }

  @Override
  public void unload(ExtensionManager em) {
    close();
    stopMusic();
  }

  static void close() {
    if (out != null) {
      try { out.close(); } catch (IOException e) { /* nothing left to save */ }
      out = null;
    }
  }

  static void need() throws ExtensionException {
    if (file == null) throw new ExtensionException("construct:start first (in setup, after reset-ticks)");
  }

  /** Where a run is written: beside the model, unless the model is in NetLogo's own Models Library (or unsaved):
   *  then in Documents/NetLogo Constructs, so NetLogo's installation stays as it came. */
  static String modelDir(Context c) {
    String d = null;
    try {
      d = c.workspace().getModelDir();
    } catch (Exception e) { /* an unsaved model */ }
    String library = System.getProperty("netlogo.models.dir");
    boolean inLibrary = false;
    try {
      inLibrary = d != null && library != null && !library.isEmpty()
          && new File(d).getCanonicalPath().startsWith(new File(library).getCanonicalPath() + File.separator);
    } catch (IOException e) { /* not comparable: beside the model */ }
    if (d != null && !d.isEmpty() && !inLibrary) return d;
    File docs = new File(new File(System.getProperty("user.home"), "Documents"), "NetLogo Constructs");
    docs.mkdirs();
    return docs.getPath();
  }

  static String slug(String s) {
    String t = s.toLowerCase().replaceAll("[^a-z0-9]+", "-").replaceAll("^-|-$", "");
    return t.isEmpty() ? "netlogo-run" : t;
  }

  // ------------------------------------------------------------------ setting up
  static class Start implements Command {
    public Syntax getSyntax() {   // construct:start "Title"   or   (construct:start "Title" "run.jsonl")
      return SyntaxJ.commandSyntax(new int[] {Syntax.StringType(), Syntax.StringType() | Syntax.RepeatableType()}, 1);
    }
    public void perform(Argument[] args, Context c) throws ExtensionException {
      start(c, args[0].getString(), args.length > 1 ? args[1].getString() : null);
    }
  }

  static void start(Context c, String runTitle, String fileName) {
      close();
      title = runTitle;
      String name = fileName != null ? fileName : slug(title) + "-run.jsonl";
      File f = new File(name);
      file = (f.isAbsolute() ? f : new File(modelDir(c), name)).getPath();
      seed = "null"; every = 1; patchVar = ""; patchEvery = 0; linkCount = -1; turtles = true; headerDone = false; lastT = Double.NaN; lastPatchT = Double.NaN; steps = 0;
      turtleVars = new ArrayList<>(); reporterNames = new ArrayList<>(); reporters = new ArrayList<>();
      new File(file).delete();
  }

  static class Seed implements Command {
    public Syntax getSyntax() { return SyntaxJ.commandSyntax(new int[] {Syntax.NumberType()}); }
    public void perform(Argument[] args, Context c) throws ExtensionException {
      seed = Dump.number(args[0].getDoubleValue());
    }
  }

  static class Every implements Command {
    public Syntax getSyntax() { return SyntaxJ.commandSyntax(new int[] {Syntax.NumberType()}); }
    public void perform(Argument[] args, Context c) throws ExtensionException {
      every = Math.max(1, args[0].getIntValue());
    }
  }

  static class TrackTurtles implements Command {   // construct:track-turtles ["infected?" "energy"]
    public Syntax getSyntax() { return SyntaxJ.commandSyntax(new int[] {Syntax.ListType()}); }
    public void perform(Argument[] args, Context c) throws ExtensionException {
      need();
      turtleVars = new ArrayList<>();
      for (Object o : args[0].getList().toJava()) {
        if (!(o instanceof String)) throw new ExtensionException("construct:track-turtles takes variable names, such as [\"energy\"]");
        turtleVars.add((String) o);
      }
    }
  }

  static class TrackReporter implements Command {   // construct:track-reporter "sheep" [-> count sheep]   (once for each)
    public Syntax getSyntax() { return SyntaxJ.commandSyntax(new int[] {Syntax.StringType(), Syntax.ReporterType()}); }
    public void perform(Argument[] args, Context c) throws ExtensionException {
      need();
      String name = args[0].getString();
      int i = reporterNames.indexOf(name);
      if (headerDone && i < 0) throw new ExtensionException("construct:track-reporter goes before the first construct:record");
      if (i >= 0) reporters.set(i, args[1].getReporter());
      else { reporterNames.add(name); reporters.add(args[1].getReporter()); }
    }
  }

  static class TrackPatches implements Command {   // construct:track-patches "pcolor" 4
    public Syntax getSyntax() { return SyntaxJ.commandSyntax(new int[] {Syntax.StringType(), Syntax.NumberType()}); }
    public void perform(Argument[] args, Context c) throws ExtensionException {
      need();
      patchVar = args[0].getString();
      patchEvery = Math.max(1, args[1].getIntValue());
    }
  }

  static class SkipTurtles implements Command {
    public Syntax getSyntax() { return SyntaxJ.commandSyntax(); }
    public void perform(Argument[] args, Context c) throws ExtensionException { need(); turtles = false; }
  }

  // ------------------------------------------------------------------ recording
  static class Record implements Command {
    public Syntax getSyntax() { return SyntaxJ.commandSyntax(); }
    public void perform(Argument[] args, Context c) throws ExtensionException {
      need();
      recordNow(c);
    }
  }

  static void recordNow(Context c) throws ExtensionException {
      org.nlogo.agent.World w = (org.nlogo.agent.World) c.world();
      boolean ticking = w.ticks() >= 0;
      double t = ticking ? w.ticks() : steps++;
      // once each time the clock moves (with `every`: each time it enters a new block of ticks), so a tick is recorded
      // once even when go stops and records again; a clock that moves in fractions (tick-advance) counts
      if (t == lastT || (every > 1 && !Double.isNaN(lastT) && Math.floor(t / every) == Math.floor(lastT / every))) return;
      lastT = t;
      try {
        if (out == null) out = new BufferedWriter(new FileWriter(file, StandardCharsets.UTF_8, true));
        if (!headerDone) {
          out.write("{\"construct-netlogo\":1,\"title\":" + json(title) + ",\"netlogo\":" + json(version())
              + ",\"seed\":" + seed + (ticking ? "" : ",\"clock\":\"steps\"") + ",\"world\":{\"min-pxcor\":" + w.minPxcor() + ",\"max-pxcor\":" + w.maxPxcor()
              + ",\"min-pycor\":" + w.minPycor() + ",\"max-pycor\":" + w.maxPycor()
              + (w instanceof org.nlogo.api.World3D ? ",\"min-pzcor\":" + ((org.nlogo.api.World3D) w).minPzcor()
                  + ",\"max-pzcor\":" + ((org.nlogo.api.World3D) w).maxPzcor() : "")
              + "}" + (w instanceof org.nlogo.api.World3D ? ",\"zcor\":true" : "") + ",\"turtle-vars\":" + jsonList(turtleVars)
              + ",\"reporters\":" + jsonList(reporterNames) + ",\"patch-reporter\":" + json(patchVar) + ",\"patch-every\":" + patchEvery
              + (track == null ? "" : ",\"music\":{\"track\":" + json(track.getName()) + ",\"path\":" + json(track.getAbsolutePath())
                  + ",\"sha256\":" + json(trackSha) + ",\"ticks-per-second\":" + tps + ",\"ticks\":" + musicTicks
                  + ",\"features\":" + json(features.getName()) + ",\"features-path\":" + json(features.getAbsolutePath())
                  + "}") + "}\n");
          headerDone = true;
        }
        StringBuilder s = new StringBuilder("{\"t\":").append(num(t));
        if (turtles) {
          s.append(",\"turtles\":[");
          List<Turtle> ts = new ArrayList<>();
          for (org.nlogo.api.Agent a : w.turtles().agents()) ts.add((Turtle) a);
          ts.sort(Comparator.comparingLong(Turtle::id));
          boolean first = true;
          for (Turtle tu : ts) {
            if (!first) s.append(',');
            first = false;
            s.append('[').append(tu.id()).append(',').append(json(breed(tu))).append(',')
                .append(num(Math.round(tu.xcor() * 1e4) / 1e4)).append(',').append(num(Math.round(tu.ycor() * 1e4) / 1e4))
                .append(',').append(value(tu.color()));
            for (String v : turtleVars) s.append(',').append(value(turtleVar(w, tu, v)));
            if (tu instanceof org.nlogo.api.Turtle3D)   // NetLogo 3D: the height last, so a 2D reader reads the rest as ever
              s.append(',').append(num(Math.round(((org.nlogo.api.Turtle3D) tu).zcor() * 1e4) / 1e4));
            s.append(']');
          }
          s.append(']');
        }
        if (!reporters.isEmpty()) {
          s.append(",\"reporters\":[");
          for (int i = 0; i < reporters.size(); i++) {
            if (i > 0) s.append(',');
            Object r = reporters.get(i);
            s.append(value(r instanceof AnonymousReporter ? ((AnonymousReporter) r).report(c, new Object[0])
                : ((java.util.function.Supplier<?>) r).get()));
          }
          s.append(']');
        }
        if (turtles && w.links().count() != linkCount) {
          linkCount = w.links().count();
          List<Link> ls = new ArrayList<>();
          for (org.nlogo.api.Agent a : w.links().agents()) ls.add((Link) a);
          ls.sort(Comparator.comparingLong((Link l) -> l.end1().id()).thenComparingLong(l -> l.end2().id()));
          s.append(",\"links\":[");
          for (int i = 0; i < ls.size(); i++) {
            Link l = ls.get(i);
            if (i > 0) s.append(',');
            s.append('[').append(l.end1().id()).append(',').append(l.end2().id()).append(',')
                .append(json(l.getBreed().printName().toLowerCase())).append(']');
          }
          s.append(']');
        }
        if (!patchVar.isEmpty() && (Double.isNaN(lastPatchT) || Math.floor(t / patchEvery) != Math.floor(lastPatchT / patchEvery))) {
          lastPatchT = t;
          int idx = w.patchesOwnIndexOf(patchVar.toUpperCase());
          if (idx < 0) throw new ExtensionException("no patch variable called " + patchVar);
          s.append(",\"patches\":[");
          int n = w.patches().count();
          for (int i = 0; i < n; i++) {
            if (i > 0) s.append(',');
            s.append(value(((Patch) w.getPatch(i)).getVariable(idx)));
          }
          s.append(']');
        }
        s.append("}\n");
        out.write(s.toString());
        out.flush();   // a run stopped half way still leaves a readable recording
      } catch (IOException e) {
        throw new ExtensionException("construct: could not write " + file + ": " + e.getMessage());
      }
  }

  static String breed(Turtle t) { return t.getBreed().printName().toLowerCase(); }

  static Object turtleVar(org.nlogo.agent.World w, Turtle t, String name) throws ExtensionException {
    String up = name.toUpperCase();
    int idx = w.breedsOwnIndexOf((org.nlogo.agent.AgentSet) t.getBreed(), up);
    if (idx < 0) idx = w.turtlesOwnIndexOf(up);
    if (idx < 0) throw new ExtensionException("no turtle variable called " + name + " (construct:track-turtles takes variable names)");
    return t.getVariable(idx);
  }

  static String version() {
    try {
      Object v = Class.forName("org.nlogo.api.Version$").getField("MODULE$").get(null);
      String s = (String) v.getClass().getMethod("versionNumberOnly").invoke(v);
      return s;
    } catch (Exception e) {
      return "7";
    }
  }

  static class Finish implements Command {
    public Syntax getSyntax() { return SyntaxJ.commandSyntax(); }
    public void perform(Argument[] args, Context c) throws ExtensionException {
      need();
      try {
        if (out == null) out = new BufferedWriter(new FileWriter(file, StandardCharsets.UTF_8, true));
        double end = c.world().ticks() >= 0 ? c.world().ticks() : Math.max(0, Double.isNaN(lastT) ? 0 : lastT);
        out.write("{\"end\":" + num(end) + "}\n");
      } catch (IOException e) {
        throw new ExtensionException("construct: could not write " + file + ": " + e.getMessage());
      }
      close();
    }
  }

  static class FileName implements Reporter {
    public Syntax getSyntax() { return SyntaxJ.reporterSyntax(Syntax.StringType()); }
    public Object report(Argument[] args, Context c) throws ExtensionException { need(); return file; }
  }

  // ------------------------------------------------------------------ drawing
  static class SetPython implements Command {
    public Syntax getSyntax() { return SyntaxJ.commandSyntax(new int[] {Syntax.StringType()}); }
    public void perform(Argument[] args, Context c) throws ExtensionException { python = args[0].getString(); }
  }

  static final List<String> OPTIONS = List.of("state", "x", "z", "change", "time", "max-agents", "smooth", "levels", "resolution", "title", "art",
      "model", "film", "window");

  /** construct:draw "phase"   or   (construct:draw "network-time" "state" "infected?" "time" "sqrt")   or   (construct:draw "phase" "smooth" 25) */
  static class Draw implements Command {
    public Syntax getSyntax() {
      return SyntaxJ.commandSyntax(new int[] {Syntax.StringType(), Syntax.WildcardType() | Syntax.RepeatableType()}, 1);
    }
    public void perform(Argument[] args, Context c) throws ExtensionException {
      need();
      if (args.length % 2 != 1) throw new ExtensionException("construct:draw takes a view, then option names and values in pairs");
      List<Object> pairs = new ArrayList<>();
      for (int i = 1; i < args.length; i++) pairs.add(args[i].get());
      for (String line : draw(args[0].getString(), pairs).split("\n"))
        if (line.contains("film") || line.startsWith("window:")) say(c, "construct: " + line);
    }
  }

  /** Draws the recording so far with a view and option pairs, builds the page and opens it; returns Construct's report. */
  static String draw(String view, List<Object> pairs) throws ExtensionException {
      if (out != null) {   // the run so far, saved
        try { out.flush(); } catch (IOException e) { /* reported below if the file is unreadable */ }
      }
      File dir = new File(new File(file).getParentFile(), slug(title) + "-construct");
      dir.mkdirs();
      List<String> draw = new ArrayList<>(List.of(python, "-m", "construct_hologram", "netlogo", file, "--view", view,
          "--out", new File(dir, "scene.json").getPath(), "--force"));
      boolean film = false;
      for (int i = 0; i < pairs.size(); i += 2) {
        Object name = pairs.get(i), v = pairs.get(i + 1);
        if (!(name instanceof String) || !OPTIONS.contains(name))
          throw new ExtensionException("construct:draw has no option " + Dump.logoObject(name, true, false) + "; it has " + String.join(", ", OPTIONS));
        String value = v instanceof Double ? num((Double) v) : v instanceof String ? (String) v : Dump.logoObject(v);
        if (name.equals("model")) {   // ("model" true): solids and a 3D model of the run, run.glb beside the page
          if (value.equals("true")) { draw.add("--solid"); draw.add("--glb"); draw.add(new File(dir, "run.glb").getPath()); }
          continue;
        }
        if (name.equals("film")) {   // ("film" true): the run as a film in Blender, film.blend beside the page
          film = value.equals("true");
          continue;
        }
        draw.add("--" + name);
        draw.add(value);
      }
      String report = run(draw, dir);
      run(List.of(python, "-m", "construct_hologram", "build", new File(dir, "scene.json").getPath(), "--out", dir.getPath()), dir);
      if (film) {   // a film needs Blender: without it, the construct is still drawn, and the reason said
        try {
          report += "\n" + run(List.of(python, "-m", "construct_hologram", "netlogo-film", file, "--blend",
              new File(dir, "film.blend").getPath()), dir, "the film");
        } catch (ExtensionException e) {
          report += "\nno film: " + e.getMessage().replace("the film: netlogo-film: ", "");
        }
      }
      File page = new File(dir, "construct.html");
      if (!GraphicsEnvironment.isHeadless() && Desktop.isDesktopSupported()) {
        try { Desktop.getDesktop().browse(page.toURI()); } catch (Exception e) { /* the page is still there */ }
      }
      return report;
  }

  static String run(List<String> cmd, File dir) throws ExtensionException { return run(cmd, dir, "construct:draw"); }

  static String run(List<String> cmd, File dir, String what) throws ExtensionException {
    File runtime = runtimeDir();
    ProcessBuilder pb = new ProcessBuilder(cmd).directory(dir).redirectErrorStream(true);
    pb.environment().put("PYTHONPATH", runtime.getPath());
    String text;
    int code;
    try {
      Process p = pb.start();
      StringBuilder sb = new StringBuilder();
      try (BufferedReader r = new BufferedReader(new InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8))) {
        String line;
        while ((line = r.readLine()) != null) sb.append(line).append('\n');
      }
      if (!p.waitFor(10, TimeUnit.MINUTES)) { p.destroy(); throw new ExtensionException(what + " took too long"); }
      code = p.exitValue();
      text = sb.toString().trim();
    } catch (IOException e) {
      throw new ExtensionException(what + " needs Python 3.10 or newer (" + python + " was not found). "
          + "Install it, or point to it with construct:set-python \"/path/to/python3\".");
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      throw new ExtensionException(what + " was interrupted");
    }
    if (code != 0) {   // Construct's own message, without its usage text
      int at = text.lastIndexOf("error: ");
      throw new ExtensionException(what + ": " + (text.isEmpty() ? "failed" : at >= 0 ? text.substring(at + 7) : text));
    }
    return text;
  }

  // ------------------------------------------------------------------ one command: run the model, draw it
  static final int SAFETY = 1000;   // go runs for a model that never stops by itself, unless construct:run-for says

  /** construct:run: setup and go as the model's own buttons do, everything worth recording, until the model stops
   *  (or SAFETY runs of go), then the view the data suits, opened. construct:run-for 3000: that many runs of go. */
  static class RunModel implements Command {
    final boolean counted;
    RunModel(boolean counted) { this.counted = counted; }
    public Syntax getSyntax() {
      return counted ? SyntaxJ.commandSyntax(new int[] {Syntax.NumberType()}) : SyntaxJ.commandSyntax();
    }
    public void perform(Argument[] args, Context c) throws ExtensionException {
      int limit = counted ? Math.max(1, args[0].getIntValue()) : track != null ? Math.max(SAFETY, musicTicks + 1) : SAFETY;
      String[] cmds = buttons(c);
      org.nlogo.agent.World w = (org.nlogo.agent.World) c.world();
      check(compiled(cmds[0], "setup", c), "setup", c);
      String model = modelName(c);
      start(c, model, null);
      autoTrack(w);
      recordNow(c);
      int runs = 0;
      boolean stopped = false;
      AnonymousCommand go = compiled(cmds[1], "go", c);
      while (runs < limit) {
        double before = w.ticks();
        check(go, "go", c);
        runs++;
        if (before >= 0 && w.ticks() == before) { stopped = true; break; }   // go stopped without a tick: the run is over
        recordNow(c);
        if (track != null && !counted && (w.ticks() >= 0 ? w.ticks() : steps) >= musicTicks) break;   // the track is over
      }
      try {
        if (out == null) out = new BufferedWriter(new FileWriter(file, StandardCharsets.UTF_8, true));
        out.write("{\"end\":" + num(Double.isNaN(lastT) ? 0 : lastT) + "}\n");
      } catch (IOException e) {
        throw new ExtensionException("construct: could not write " + file + ": " + e.getMessage());
      }
      close();
      say(c, stopped ? "construct: " + model + " stopped by itself after " + runs + " runs of " + cmds[1].split("\\s+")[0] + "; drawing it."
          : track != null && !counted ? "construct: ran " + model + " for the length of " + track.getName() + " (" + runs + " runs of go); drawing it."
          : counted ? "construct: ran " + model + " for " + runs + " runs of go; drawing it."
          : "construct: " + model + " was still running after " + runs + " runs of go; drew those. For a longer run: construct:run-for 3000");
      String report = draw("auto", new ArrayList<>());
      for (String line : report.split("\n")) if (line.startsWith("view:") || line.startsWith("window:")) say(c, "construct: " + line);
    }
  }

  // ------------------------------------------------------------------ music: a tick is a moment of the track

  /** construct:music "track.mp3"   or   (construct:music "track.mp3" 24)   (ticks a second, 30 by default);
   *  construct:music "" forgets it. The track is analysed once (construct audio, with ffmpeg) into a features
   *  file beside the run; a track beside the model can be named alone. */
  static class Music implements Command {
    public Syntax getSyntax() {
      return SyntaxJ.commandSyntax(new int[] {Syntax.StringType(), Syntax.NumberType() | Syntax.RepeatableType()}, 1);
    }
    public void perform(Argument[] args, Context c) throws ExtensionException {
      String name = args[0].getString();
      stopMusic();   // another track, or none: the one playing stops
      if (name.isEmpty()) { track = null; features = null; music = new HashMap<>(); musicTicks = 0; return; }
      int rate = args.length > 1 ? args[1].getIntValue() : 30;
      if (rate < 1 || rate > 120) throw new ExtensionException("construct:music: ticks a second is 1 to 120, not " + rate);
      File f = new File(name);
      if (!f.isAbsolute()) {
        try { f = new File(c.attachCurrentDirectory(name)); } catch (IOException e) { /* as it is */ }
      }
      if (!f.isFile()) throw new ExtensionException("construct:music: there is no file " + f.getPath());
      String sha;
      try { sha = sha256(f); } catch (IOException e) { throw new ExtensionException("construct:music could not read " + f.getPath()); }
      // keyed by the track's fingerprint: two different files of one name never share their features
      File out = new File(modelDir(c), slug(f.getName().replaceAll("\\.[^.]+$", "")) + "-" + sha.substring(0, 8) + "-audio-" + rate + ".json");
      if (!out.isFile() || out.lastModified() < f.lastModified())
        run(List.of(python, "-m", "construct_hologram", "audio", f.getAbsolutePath(), "--fps", String.valueOf(rate),
            "--out", out.getPath()), out.getParentFile(), "construct:music");
      Map<String, double[]> m = new HashMap<>();
      try {
        String doc = Files.readString(out.toPath(), StandardCharsets.UTF_8);
        for (String key : List.of("energy", "high", "kick", "onset")) {
          Matcher mm = Pattern.compile("\"" + key + "\":\\[([^\\]]*)\\]").matcher(doc);
          if (!mm.find()) throw new ExtensionException("construct:music: " + out.getName() + " has no " + key
              + "; delete it and run construct:music again");
          String body = mm.group(1).trim();
          String[] xs = body.isEmpty() ? new String[0] : body.split(",");
          double[] v = new double[xs.length];
          for (int i = 0; i < xs.length; i++) v[i] = Double.parseDouble(xs[i].trim());
          m.put(key, v);
        }
        trackSha = sha;
      } catch (IOException | NumberFormatException e) {
        throw new ExtensionException("construct:music could not read " + out.getPath() + ": " + e.getMessage());
      }
      track = f; features = out; tps = rate; music = m; musicTicks = m.get("energy").length;
      say(c, "construct: " + f.getName() + ", " + num(Math.round(musicTicks * 10.0 / rate) / 10.0) + " s: " + musicTicks
          + " ticks at " + rate + " a second");
    }
  }

  static String sha256(File f) throws IOException {
    try {
      byte[] d = MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(f.toPath()));
      StringBuilder s = new StringBuilder();
      for (byte b : d) s.append(String.format("%02x", b));
      return s.toString();
    } catch (java.security.NoSuchAlgorithmException e) {
      throw new IOException(e);
    }
  }

  static double musicClock(Context c) {
    return c.world().ticks() >= 0 ? c.world().ticks() : steps;
  }

  /** construct:kick, construct:energy, construct:high, construct:hit: the music at this tick, 0 to 1 (0 after the track). */
  static class MusicAt implements Reporter {
    final String key;
    MusicAt(String key) { this.key = key; }
    public Syntax getSyntax() { return SyntaxJ.reporterSyntax(Syntax.NumberType()); }
    public Object report(Argument[] args, Context c) throws ExtensionException {
      if (track == null) throw new ExtensionException("construct:music \"track.mp3\" first");
      double[] v = music.get(key);
      if (liveTo >= 0) {   // live, the model behind the track: what is heard now; a kick or hit since the last tick
        double x = liveTo < v.length ? v[liveTo] : 0.0;
        if (key.equals("kick") || key.equals("onset"))
          for (int i = Math.max(0, liveFrom + 1); i < Math.min(liveTo, v.length); i++) x = Math.max(x, v[i]);
        return x;
      }
      int i = (int) Math.floor(musicClock(c));
      return i >= 0 && i < v.length ? v[i] : 0.0;
    }
  }

  /** construct:music-time: the seconds of the track at this tick. */
  static class MusicTime implements Reporter {
    public Syntax getSyntax() { return SyntaxJ.reporterSyntax(Syntax.NumberType()); }
    public Object report(Argument[] args, Context c) throws ExtensionException {
      if (track == null) throw new ExtensionException("construct:music \"track.mp3\" first");
      return (liveTo >= 0 ? liveTo : musicClock(c)) / tps;
    }
  }

  // ------------------------------------------------------------------ live: the track heard while NetLogo runs

  static javax.sound.sampled.Clip clip = null;
  static long playStart = 0;
  static double playFrom = 0;
  static boolean playing = false;
  /** A model slower than its track (in the window, redrawing the view) cannot keep its ticks' moments: while it is
   *  behind, it follows the music heard instead, from the frame after liveFrom to liveTo (-1: in time, tick by tick). */
  static int liveFrom = -1, liveTo = -1;
  static boolean saidBehind = false;

  /** construct:play: the track from the current tick's moment, heard as the model runs (with construct:sync in go).
   *  Without an audio output (a server, a headless run), the run keeps time with the clock instead. */
  static class Play implements Command {
    public Syntax getSyntax() { return SyntaxJ.commandSyntax(); }
    public void perform(Argument[] args, Context c) throws ExtensionException {
      if (track == null) throw new ExtensionException("construct:music \"track.mp3\" first");
      stopMusic();
      playFrom = Math.max(0, musicClock(c)) / tps;
      File wav = new File(features.getParentFile(), features.getName().replaceAll("-audio-\\d+\\.json$", "") + "-play.wav");
      try {
        if (System.getenv("CONSTRUCT_SILENT") != null) throw new IOException("CONSTRUCT_SILENT is set");
        if (!wav.isFile() || wav.lastModified() < track.lastModified()) {
          Process p = new ProcessBuilder(ffmpeg(), "-v", "error", "-y", "-i", track.getAbsolutePath(), "-ac", "2", "-ar",
              "44100", "-sample_fmt", "s16", wav.getAbsolutePath()).redirectErrorStream(true).start();
          if (!p.waitFor(5, TimeUnit.MINUTES) || p.exitValue() != 0) throw new IOException("ffmpeg could not convert the track");
        }
        javax.sound.sampled.Clip cl = javax.sound.sampled.AudioSystem.getClip();
        try (javax.sound.sampled.AudioInputStream in = javax.sound.sampled.AudioSystem.getAudioInputStream(wav)) {
          cl.open(in);   // the clip holds the sound; the file is free again (Windows locks open files)
        }
        cl.setMicrosecondPosition((long) (playFrom * 1e6));
        cl.start();
        clip = cl;
      } catch (Exception e) {   // no sound here: keep time with the clock
        clip = null;
        say(c, "construct: no sound (" + e.getMessage() + "); the run keeps time with the clock");
      }
      playStart = System.nanoTime();
      playing = true;
    }
  }

  /** ffmpeg: $CONSTRUCT_FFMPEG, the PATH, or where it is usually installed (NetLogo opened from the Finder does not
   *  see a shell's PATH). */
  static String ffmpeg() throws IOException {
    List<String> cands = new ArrayList<>();
    if (System.getenv("CONSTRUCT_FFMPEG") != null) cands.add(System.getenv("CONSTRUCT_FFMPEG"));
    String path = System.getenv("PATH");
    boolean win = System.getProperty("os.name", "").toLowerCase().contains("win");
    if (path != null) for (String d : path.split(File.pathSeparator)) cands.add(new File(d, win ? "ffmpeg.exe" : "ffmpeg").getPath());
    cands.addAll(List.of("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg", "C:\\ffmpeg\\bin\\ffmpeg.exe"));
    for (String c : cands) if (new File(c).canExecute()) return c;
    throw new IOException("ffmpeg is needed: install it (macOS: brew install ffmpeg) or set CONSTRUCT_FFMPEG");
  }

  static double heard() {
    return clip != null ? clip.getMicrosecondPosition() / 1e6 : playFrom + (System.nanoTime() - playStart) / 1e9;
  }

  /** construct:sync (in go, after tick): wait until the track reaches this tick, so the run moves in time with it.
   *  Does nothing unless construct:play has started the track. */
  static class Sync implements Command {
    public Syntax getSyntax() { return SyntaxJ.commandSyntax(); }
    public void perform(Argument[] args, Context c) throws ExtensionException {
      if (!playing) return;
      double target = musicClock(c) / tps;
      try {
        for (double now = heard(); now < target && playing; now = heard()) {
          if (clip != null && !clip.isRunning() && clip.getMicrosecondPosition() >= clip.getMicrosecondLength()) break;   // the track is over
          Thread.sleep(Math.max(1, Math.min(20, (long) ((target - now) * 1000))));
        }
      } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
      }
      int now = (int) Math.floor(heard() * tps), at = (int) Math.floor(musicClock(c));
      if (playing && now > at + 1) {   // more than a tick behind the track: follow what is heard
        liveFrom = liveTo >= 0 ? liveTo : at - 1;
        liveTo = now;
        if (!saidBehind) {
          saidBehind = true;
          say(c, "construct: this model runs slower here than its track's " + (int) tps + " ticks a second, so it follows "
              + "the music as you hear it (construct:run keeps every tick at its moment)");
        }
      } else {
        liveFrom = liveTo = -1;
      }
    }
  }

  /** construct:stop-music: stop the track (construct:play starts it again from the current tick). */
  static class StopMusic implements Command {
    public Syntax getSyntax() { return SyntaxJ.commandSyntax(); }
    public void perform(Argument[] args, Context c) { stopMusic(); }
  }

  static void stopMusic() {
    playing = false;
    liveFrom = liveTo = -1;
    saidBehind = false;
    if (clip != null) {
      clip.stop();
      clip.close();
      clip = null;
    }
  }

  /** The model's own code as an anonymous command, compiled once in the running context (so its random numbers
   *  and agents are the model's own, as when its buttons are pressed). */
  static AnonymousCommand compiled(String code, String what, Context c) throws ExtensionException {
    try {
      org.nlogo.nvm.ExtensionContext ec = (org.nlogo.nvm.ExtensionContext) c;
      org.nlogo.nvm.Context ctx = ec.nvmContext();
      org.nlogo.nvm.Procedure p = ec.workspace().compileForRun("[ -> " + code + "\n]", ctx, true);
      return (AnonymousCommand) ctx.callReporterProcedure(org.nlogo.nvm.Activation.forRunOrRunresult(p, ctx.activation, ctx.ip));
    } catch (Exception e) {
      throw new ExtensionException("construct:run could not use the model's " + what + " (" + code + "): " + e.getMessage());
    }
  }

  static void check(AnonymousCommand cmd, String what, Context c) throws ExtensionException {
    try {
      cmd.perform(c, new Object[0]);
    } catch (org.nlogo.api.LogoException e) {
      throw new ExtensionException("construct:run: the model's " + what + " failed: " + e.getMessage());
    }
  }

  static void say(Context c, String text) {
    try {
      c.workspace().outputObject(text, null, true, false, org.nlogo.api.OutputDestinationJ.NORMAL());
    } catch (Exception e) { /* nowhere to say it: the page still opens */ }
  }

  static String modelName(Context c) {
    try {
      String path = c.workspace().getModelPath();
      if (path != null && !path.isEmpty()) return new File(path).getName().replaceAll("\\.nlogox?(3d)?$", "");
    } catch (Exception e) { /* an unsaved model */ }
    return "NetLogo run";
  }

  /** setup and go: the model's own buttons (their whole command), else setup and go by name. */
  static String[] buttons(Context c) {
    String setup = null, go = null, turtleGo = null, step = null;
    List<String[]> found = new ArrayList<>();   // command, forever?, kind
    try {
      String path = c.workspace().getModelPath();
      if (path != null && new File(path).isFile()) {
        String text = new String(java.nio.file.Files.readAllBytes(new File(path).toPath()), StandardCharsets.UTF_8);
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("<button([^>]*)>([^<]*)</button>").matcher(text);
        while (m.find()) {
          String cmd = m.group(2).replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", "\"").replace("&amp;", "&").trim();
          java.util.regex.Matcher k = java.util.regex.Pattern.compile("kind=\"(\\w+)\"").matcher(m.group(1));
          if (!cmd.isEmpty()) found.add(new String[] {cmd, String.valueOf(m.group(1).contains("forever=\"true\"")), k.find() ? k.group(1) : "Observer"});
        }
      }
    } catch (IOException e) { /* no file: the names */ }
    for (String[] b : found) {
      boolean forever = b[1].equals("true"), observer = b[2].equals("Observer");
      String first = b[0].split("\\s+")[0].toLowerCase();
      if (observer && !forever && setup == null && first.equals("setup")) setup = b[0];
      if (observer && forever && go == null && first.equals("go")) go = b[0];
      if (!observer && forever && turtleGo == null && b[2].equals("Turtle")) turtleGo = "ask turtles [ " + b[0] + " ]";
      if (observer && !forever && step == null && b[0].matches("(?is).*\\b(go|step|iterate|run|once|next).*")
          && !b[0].matches("(?is).*\\b(setup|reset|clear).*")) step = b[0];
    }
    for (int pass = 0; pass < 2; pass++)   // a setup button by another name; one that fills the world before one that empties it
      for (String[] b : found)
        if (setup == null && b[2].equals("Observer") && b[1].equals("false") && b[0].matches("(?is).*\\b(setup|reset|init|new|start).*")
            && (pass == 1 || !b[0].matches("(?is).*(blank|clear|empty|erase).*"))) setup = b[0];
    for (String[] b : found)
      if (go == null && b[2].equals("Observer") && b[1].equals("true")) go = b[0];
    return new String[] {setup != null ? setup : "setup", go != null ? go : turtleGo != null ? turtleGo : step != null ? step : "go"};
  }

  /** What to record without being told: each turtle variable that is true or false, each breed's count, patch colours. */
  static void autoTrack(org.nlogo.agent.World w) {
    turtleVars = new ArrayList<>();
    List<String> own = scala.jdk.javaapi.CollectionConverters.asJava(w.program().turtlesOwn());
    Turtle any = null;
    for (org.nlogo.api.Agent a : w.turtles().agents()) { any = (Turtle) a; break; }
    for (int i = 13; i < own.size() && any != null; i++) {   // past NetLogo's 13 built-in turtle variables
      Object v = any.getVariable(w.turtlesOwnIndexOf(own.get(i)));
      if (v instanceof Boolean) turtleVars.add(own.get(i).toLowerCase());
    }
    for (org.nlogo.api.Agent a : w.turtles().agents())   // a model that hides turtles (an unlit firefly): which, tick by tick
      if (((Turtle) a).hidden()) { turtleVars.add("hidden?"); break; }
    reporterNames = new ArrayList<>(); reporters = new ArrayList<>();
    for (String b : scala.jdk.javaapi.CollectionConverters.asJava(w.program().breeds()).keySet()) {
      final org.nlogo.agent.AgentSet set = w.getBreed(b);
      if (set == null) continue;
      reporterNames.add("count " + b.toLowerCase());
      reporters.add((java.util.function.Supplier<Object>) () -> (double) set.count());
    }
    if (w instanceof org.nlogo.api.World3D) { patchVar = ""; patchEvery = 0; return; }   // 3D: the views draw no 3D patches
    int n = w.patches().count();
    patchVar = "pcolor";
    patchEvery = Math.max(1, Math.min(4, (int) Math.ceil(n / 16000.0)));   // a large world: its colours every few ticks
  }

  /** The folder that holds the bundled construct_hologram package: beside construct.jar. */
  static File runtimeDir() {
    try {
      return new File(ConstructExtension.class.getProtectionDomain().getCodeSource().getLocation().toURI()).getParentFile();
    } catch (Exception e) {
      return new File(".");
    }
  }

  // ------------------------------------------------------------------ JSON
  static String num(double d) { return Dump.number(d); }

  static String json(String s) {
    StringBuilder b = new StringBuilder("\"");
    for (char ch : s.toCharArray()) {
      if (ch == '"' || ch == '\\') b.append('\\').append(ch);
      else if (ch < 0x20) b.append(String.format("\\u%04x", (int) ch));
      else b.append(ch);
    }
    return b.append('"').toString();
  }

  static String jsonList(List<String> xs) {
    StringBuilder b = new StringBuilder("[");
    for (int i = 0; i < xs.size(); i++) { if (i > 0) b.append(','); b.append(json(xs.get(i))); }
    return b.append(']').toString();
  }

  /** A NetLogo value as JSON: numbers, booleans, strings, lists, a turtle as its who, a patch as [x y], else null. */
  static String value(Object v) {
    if (v instanceof Double) return num((Double) v);
    if (v instanceof Number) return num(((Number) v).doubleValue());
    if (v instanceof Boolean) return v.toString();
    if (v instanceof String) return json((String) v);
    if (v instanceof LogoList) {
      StringBuilder b = new StringBuilder("[");
      int i = 0;
      for (Object x : ((LogoList) v).toJava()) { if (i++ > 0) b.append(','); b.append(value(x)); }
      return b.append(']').toString();
    }
    if (v instanceof Turtle) return Long.toString(((Turtle) v).id());
    if (v instanceof Patch) return "[" + ((Patch) v).pxcor() + "," + ((Patch) v).pycor() + "]";
    return "null";
  }
}
