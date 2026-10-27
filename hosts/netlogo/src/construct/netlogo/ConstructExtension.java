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
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.concurrent.TimeUnit;

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
 */
public class ConstructExtension extends DefaultClassManager {

  // ------------------------------------------------------------------ the recording's state
  static String file = null, title = "", seed = "null", patchVar = "";
  static int every = 1, patchEvery = 0, linkCount = -1;
  static double lastT = Double.NaN;
  static long steps = 0;   // the clock of a model that never starts the tick counter
  static boolean turtles = true, headerDone = false;
  static List<String> turtleVars = new ArrayList<>();
  static List<String> reporterNames = new ArrayList<>();
  static List<AnonymousReporter> reporters = new ArrayList<>();
  static BufferedWriter out = null;
  static String python = System.getProperty("os.name", "").toLowerCase().contains("win") ? "python" : "python3";

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
  }

  @Override
  public void unload(ExtensionManager em) {
    close();
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

  static String modelDir(Context c) {
    try {
      String d = c.workspace().getModelDir();
      if (d != null && !d.isEmpty()) return d;
    } catch (Exception e) { /* an unsaved model */ }
    return System.getProperty("user.dir");
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
      close();
      title = args[0].getString();
      String name = args.length > 1 ? args[1].getString() : slug(title) + "-run.jsonl";
      File f = new File(name);
      file = (f.isAbsolute() ? f : new File(modelDir(c), name)).getPath();
      seed = "null"; every = 1; patchVar = ""; patchEvery = 0; linkCount = -1; turtles = true; headerDone = false; lastT = Double.NaN; steps = 0;
      turtleVars = new ArrayList<>(); reporterNames = new ArrayList<>(); reporters = new ArrayList<>();
      new File(file).delete();
    }
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
      org.nlogo.agent.World w = (org.nlogo.agent.World) c.world();
      boolean ticking = w.ticks() >= 0;
      double t = ticking ? w.ticks() : steps++;
      if (((long) t) % every != 0 || t == lastT) return;   // once a tick, even when a model's go stops and records again
      lastT = t;
      try {
        if (out == null) out = new BufferedWriter(new FileWriter(file, StandardCharsets.UTF_8, true));
        if (!headerDone) {
          out.write("{\"construct-netlogo\":1,\"title\":" + json(title) + ",\"netlogo\":" + json(version())
              + ",\"seed\":" + seed + (ticking ? "" : ",\"clock\":\"steps\"") + ",\"world\":{\"min-pxcor\":" + w.minPxcor() + ",\"max-pxcor\":" + w.maxPxcor()
              + ",\"min-pycor\":" + w.minPycor() + ",\"max-pycor\":" + w.maxPycor() + "},\"turtle-vars\":" + jsonList(turtleVars)
              + ",\"reporters\":" + jsonList(reporterNames) + ",\"patch-reporter\":" + json(patchVar) + ",\"patch-every\":" + patchEvery + "}\n");
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
            s.append(']');
          }
          s.append(']');
        }
        if (!reporters.isEmpty()) {
          s.append(",\"reporters\":[");
          for (int i = 0; i < reporters.size(); i++) {
            if (i > 0) s.append(',');
            s.append(value(reporters.get(i).report(c, new Object[0])));
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
        if (!patchVar.isEmpty() && ((long) t) % patchEvery == 0) {
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

  static final List<String> OPTIONS = List.of("state", "x", "z", "change", "time", "max-agents", "smooth", "levels", "resolution", "title", "art");

  /** construct:draw "phase"   or   (construct:draw "network-time" "state" "infected?" "time" "sqrt")   or   (construct:draw "phase" "smooth" 25) */
  static class Draw implements Command {
    public Syntax getSyntax() {
      return SyntaxJ.commandSyntax(new int[] {Syntax.StringType(), Syntax.WildcardType() | Syntax.RepeatableType()}, 1);
    }
    public void perform(Argument[] args, Context c) throws ExtensionException {
      need();
      if (out != null) {   // the run so far, saved
        try { out.flush(); } catch (IOException e) { /* reported below if the file is unreadable */ }
      }
      if (args.length % 2 != 1) throw new ExtensionException("construct:draw takes a view, then option names and values in pairs");
      File dir = new File(new File(file).getParentFile(), slug(title) + "-construct");
      dir.mkdirs();
      List<String> draw = new ArrayList<>(List.of(python, "-m", "construct_hologram", "netlogo", file, "--view", args[0].getString(),
          "--out", new File(dir, "scene.json").getPath(), "--force"));
      for (int i = 1; i < args.length; i += 2) {
        Object name = args[i].get(), v = args[i + 1].get();
        if (!(name instanceof String) || !OPTIONS.contains(name))
          throw new ExtensionException("construct:draw has no option " + Dump.logoObject(name, true, false) + "; it has " + String.join(", ", OPTIONS));
        draw.add("--" + name);
        draw.add(v instanceof Double ? num((Double) v) : v instanceof String ? (String) v : Dump.logoObject(v));
      }
      run(draw, dir);
      run(List.of(python, "-m", "construct_hologram", "build", new File(dir, "scene.json").getPath(), "--out", dir.getPath()), dir);
      File page = new File(dir, "construct.html");
      if (!GraphicsEnvironment.isHeadless() && Desktop.isDesktopSupported()) {
        try { Desktop.getDesktop().browse(page.toURI()); } catch (Exception e) { /* the page is still there */ }
      }
    }
  }

  static void run(List<String> cmd, File dir) throws ExtensionException {
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
      if (!p.waitFor(10, TimeUnit.MINUTES)) { p.destroy(); throw new ExtensionException("construct:draw took too long"); }
      code = p.exitValue();
      text = sb.toString().trim();
    } catch (IOException e) {
      throw new ExtensionException("construct:draw needs Python 3.10 or newer (" + python + " was not found). "
          + "Install it, or point to it with construct:set-python \"/path/to/python3\".");
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      throw new ExtensionException("construct:draw was interrupted");
    }
    if (code != 0) {   // Construct's own message, without its usage text
      int at = text.lastIndexOf("error: ");
      throw new ExtensionException("construct:draw: " + (text.isEmpty() ? "failed" : at >= 0 ? text.substring(at + 7) : text));
    }
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
