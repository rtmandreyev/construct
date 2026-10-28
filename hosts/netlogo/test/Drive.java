// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Artyom Andreyev
import org.nlogo.headless.HeadlessWorkspace;

/** Opens a model headless and runs commands in order, printing the first error NetLogo raises (exit 1).
 *  BehaviorSpace's headless runs keep going past errors, so the extension's tests drive NetLogo this way.
 *    java -cp netlogo.jar:. Drive MODEL "command" ["command" ...]   (a .nlogox3d model opens in NetLogo 3D) */
public class Drive {
  public static void main(String[] args) throws Exception {
    HeadlessWorkspace ws = HeadlessWorkspace.newInstance(args[0].endsWith(".nlogox3d") || args[0].endsWith(".nlogo3d"));   // NetLogo 3D
    int code = 0;
    try {
      ws.open(args[0], false);
      for (int i = 1; i < args.length; i++) ws.command(args[i]);
    } catch (Exception e) {
      System.out.println("ERROR: " + e.getMessage());
      code = 1;
    } finally {
      ws.dispose();
    }
    System.exit(code);
  }
}
