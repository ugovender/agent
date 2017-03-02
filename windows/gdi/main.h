/*
This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
*/

#include <windows.h>

#ifndef GDI_H_
#define	GDI_H_

typedef void (*CallbackTypeRepaint)(int id, int x,int y,int w, int h);
typedef void (*CallbackTypeKeyboard)(int id, wchar_t* type, wchar_t* c, bool shift,bool ctrl,bool alt,bool meta);
typedef void (*CallbackTypeMouse)(int id, wchar_t* type, int x, int y, int button);
typedef bool (*CallbackTypeWindow)(int id, wchar_t* type);
typedef void (*CallbackTypeTimer)();

extern "C"{
  __declspec(dllexport) void setCallbackRepaint(CallbackTypeRepaint callback);
  __declspec(dllexport) void setCallbackKeyboard(CallbackTypeKeyboard callback);
  __declspec(dllexport) void setCallbackMouse(CallbackTypeMouse callback);
  __declspec(dllexport) void setCallbackTimer(CallbackTypeTimer callback);
  __declspec(dllexport) void setCallbackWindow(CallbackTypeWindow callback);
  __declspec(dllexport) void loop();
  __declspec(dllexport) int newWindow(int tp,int x, int y, int w, int h, wchar_t* iconPath);
  __declspec(dllexport) void destroyWindow(int id);
  __declspec(dllexport) void setTitle(int id, wchar_t* title);
  __declspec(dllexport) void show(int id,int md);
  __declspec(dllexport) void toFront(int id);
  __declspec(dllexport) void hide(int id);
  __declspec(dllexport) void penColor(int id, int r, int g, int b);
  __declspec(dllexport) void penWidth(int id, int w);
  __declspec(dllexport) void drawLine(int id, int x1, int y1, int x2,int y2);
  __declspec(dllexport) void drawEllipse(int id, int x, int y, int w,int h);
  __declspec(dllexport) void fillEllipse(int id, int x, int y, int w,int h);
  __declspec(dllexport) void drawText(int id, wchar_t* str, int x, int y);
  __declspec(dllexport) void fillRectangle(int id, int x, int y, int w,int h);
  
  __declspec(dllexport) void getScreenSize(int* size);
  
  __declspec(dllexport) int getTextHeight(int id);
  __declspec(dllexport) int getTextWidth(int id,wchar_t*);

  __declspec(dllexport) void repaint(int id, int x, int y, int w,int h);
  __declspec(dllexport) void clipRectangle(int id, int x, int y, int w, int h);
  __declspec(dllexport) void clearClipRectangle(int id);
  
  __declspec(dllexport) void setClipboardText(wchar_t* str);
  __declspec(dllexport) wchar_t* getClipboardText();

  __declspec(dllexport) void createNotifyIcon(int id,wchar_t* iconPath,wchar_t* toolTip);
  __declspec(dllexport) void updateNotifyIcon(int id,wchar_t* iconPath,wchar_t* toolTip);
  __declspec(dllexport) void destroyNotifyIcon(int id);

  __declspec(dllexport) void getMousePosition(int* pos);

  __declspec(dllexport) BOOL isUserInAdminGroup();
  __declspec(dllexport) BOOL isRunAsAdmin();
  __declspec(dllexport) BOOL isProcessElevated();
  __declspec(dllexport) BOOL isTaskRunning(int pid);

  /*__declspec(dllexport) void update(wchar_t* iconPath,wchar_t* toolTip);
  __declspec(dllexport) void hide();
  __declspec(dllexport) void clearMenu();
  __declspec(dllexport) void insertMenu(int id,wchar_t* name);
  __declspec(dllexport) void showContextMenu();
  __declspec(dllexport) void setCallback(CallbackType callback);*/
}

#endif	/* GDI_H_ */
