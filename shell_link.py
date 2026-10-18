"""Unicode Shell Link adapter; WScript.Shell uses ANSI paths on some locales."""
UNICODE_SHELL = r'''
Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Text;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
[ComImport, Guid("00021401-0000-0000-C000-000000000046")]
class BmsShellLinkClass {}
[ComImport, Guid("000214F9-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IBmsShellLinkW {
 void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path,int count,IntPtr data,uint flags);
 void GetIDList(out IntPtr list); void SetIDList(IntPtr list);
 void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder text,int count);
 void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string text);
 void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path,int count);
 void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string path);
 void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder text,int count);
 void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string text);
 void GetHotkey(out short value); void SetHotkey(short value);
 void GetShowCmd(out int value); void SetShowCmd(int value);
 void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path,int count,out int index);
 void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string path,int index);
 void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string path,uint reserved);
 void Resolve(IntPtr window,uint flags);
 void SetPath([MarshalAs(UnmanagedType.LPWStr)] string path);
}
public sealed class BmsShortcut {
 readonly IBmsShellLinkW link;
 readonly string file;
 public BmsShortcut(string path) {
  file=path;link=(IBmsShellLinkW)new BmsShellLinkClass();
  if(File.Exists(path))((IPersistFile)link).Load(path,0);
 }
 public string TargetPath { get {var b=new StringBuilder(32768);link.GetPath(b,b.Capacity,IntPtr.Zero,0);return b.ToString();} set{link.SetPath(value);} }
 public string Arguments { get {var b=new StringBuilder(32768);link.GetArguments(b,b.Capacity);return b.ToString();} set{link.SetArguments(value);} }
 public string WorkingDirectory { get {var b=new StringBuilder(32768);link.GetWorkingDirectory(b,b.Capacity);return b.ToString();} set{link.SetWorkingDirectory(value);} }
 public string Description { get {var b=new StringBuilder(32768);link.GetDescription(b,b.Capacity);return b.ToString();} set{link.SetDescription(value);} }
 public string IconLocation {
  get {var b=new StringBuilder(32768);int i;link.GetIconLocation(b,b.Capacity,out i);return b.ToString()+","+i;}
  set {int i=0;string path=value;int comma=value.LastIndexOf(',');if(comma>=0 && Int32.TryParse(value.Substring(comma+1),out i))path=value.Substring(0,comma);link.SetIconLocation(path,i);}
 }
 public int WindowStyle { get {int v;link.GetShowCmd(out v);return v;} set {link.SetShowCmd(value);} }
 public void Save(){((IPersistFile)link).Save(file,true);}
}
public sealed class BmsShell {
 public BmsShortcut CreateShortcut(string path){return new BmsShortcut(path);}
}
'@
'''
