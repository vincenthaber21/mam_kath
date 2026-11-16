import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { StatusBar } from "expo-status-bar";
import React from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { AuthProvider, useAuth } from "./src/AuthContext";
import CaptureScreen from "./src/screens/CaptureScreen";
import HistoryScreen from "./src/screens/HistoryScreen";
import LoginScreen from "./src/screens/LoginScreen";
import ResultScreen from "./src/screens/ResultScreen";
import { colors } from "./src/theme";

const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator();
const RootStack = createNativeStackNavigator();

function AccountButton({ navigation }) {
  const { isSignedIn } = useAuth();
  return (
    <Pressable onPress={() => navigation.navigate("Login")} hitSlop={8} style={{ marginRight: 4, padding: 6 }}>
      <Text style={{ color: colors.brand, fontWeight: "700", fontSize: 14 }}>
        {isSignedIn ? "Account" : "Sign in"}
      </Text>
    </Pressable>
  );
}

function ReportStack() {
  return (
    <Stack.Navigator>
      <Stack.Screen
        name="Capture"
        component={CaptureScreen}
        options={({ navigation }) => ({
          title: "Report",
          headerStyle: { backgroundColor: colors.bg },
          headerShadowVisible: false,
          headerRight: () => <AccountButton navigation={navigation} />,
        })}
      />
      <Stack.Screen
        name="Result"
        component={ResultScreen}
        options={{ title: "Result", headerStyle: { backgroundColor: colors.bg }, headerShadowVisible: false }}
      />
    </Stack.Navigator>
  );
}

function HistoryStack() {
  return (
    <Stack.Navigator>
      <Stack.Screen
        name="History"
        component={HistoryScreen}
        options={{ headerShown: false }}
      />
      <Stack.Screen
        name="Result"
        component={ResultScreen}
        options={{ title: "Result", headerStyle: { backgroundColor: colors.bg }, headerShadowVisible: false }}
      />
    </Stack.Navigator>
  );
}

function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.brand,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: { borderTopColor: colors.border },
      }}
    >
      <Tab.Screen
        name="ReportTab"
        component={ReportStack}
        options={{
          title: "Report",
          tabBarIcon: ({ color }) => <Text style={{ color, fontSize: 18 }}>◎</Text>,
        }}
      />
      <Tab.Screen
        name="HistoryTab"
        component={HistoryStack}
        options={{
          title: "My reports",
          tabBarIcon: ({ color }) => <Text style={{ color, fontSize: 18 }}>☰</Text>,
        }}
      />
    </Tab.Navigator>
  );
}

function Root() {
  const { ready } = useAuth();
  if (!ready) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bg }}>
        <ActivityIndicator color={colors.brand} />
      </View>
    );
  }
  return (
    <RootStack.Navigator>
      <RootStack.Screen name="Main" component={MainTabs} options={{ headerShown: false }} />
      <RootStack.Screen
        name="Login"
        component={LoginScreen}
        options={{
          presentation: "modal",
          title: "Account",
          headerStyle: { backgroundColor: colors.bg },
          headerShadowVisible: false,
        }}
      />
    </RootStack.Navigator>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <NavigationContainer>
          <StatusBar style="dark" />
          <Root />
        </NavigationContainer>
      </AuthProvider>
    </SafeAreaProvider>
  );
}
