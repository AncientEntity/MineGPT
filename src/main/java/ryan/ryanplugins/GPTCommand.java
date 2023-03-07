package ryan.ryanplugins;

import org.bukkit.ChatColor;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.IOException;
import java.util.Arrays;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import java.io.*;
import java.net.*;

public class GPTCommand implements CommandExecutor {

    public static String[] currentCommands = new String[0];


    @Override
    public boolean onCommand(CommandSender sender, Command cmd, String label, String[] args) {
        Player player = (Player)sender;

        if(sender instanceof Player) {

            if(args[0].equals("kill")) {
                currentCommands = new String[0];
                player.sendMessage(ChatColor.translateAlternateColorCodes('&', "Previous GPT Killed."));
                return true;

            }
            if(args[0].equals("local") || args[0].equals("proxy")) {
                useLocal = !useLocal;
                if(useLocal) {
                    player.sendMessage(ChatColor.translateAlternateColorCodes('&', "Now using local."));
                } else {
                    player.sendMessage(ChatColor.translateAlternateColorCodes('&', "Now using proxy."));
                }
                return true;

            }

            String response = Arrays.toString(generateCommands(ArrayToString(args)));
            player.sendMessage(ChatColor.translateAlternateColorCodes('&',response));

            return true;
        }


        return false;
    }

    public static String[] generateCommands(String prompt) {
        String totalPrompt = "You are an expert in writing minecraft commands. The user gives you a prompt and you turn it into minecraft commands for minecraft the game. Don't give any details or explanation about the code you've written, only give the commands. Format it in a numbered list. These commands will be chained into commands blocks and be executed every tick. Prompt: "+prompt+". Commands:";
        try {
            String response = generateResponse(totalPrompt);
            String[] commands = splitter(response);


            return commands;
        } catch (Exception e) {
            System.out.println(e);
        }
        return new String[0];
    }

    private static final String API_URL = "https://chatgpt-api.shn.hk/v1/";
    private static boolean useLocal = true; //If you have a chatGPT wrapper locally setup.

    public static String generateResponse(String prompt) throws IOException {

        if(useLocal) {
            return RequestGPTFromLocal(prompt);
        }

        // Set up the HTTP connection
        URL url = new URL(API_URL);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setRequestMethod("POST");
        connection.setRequestProperty("Content-Type", "application/json");
        //connection.setRequestProperty("Authorization", "Bearer AUTH HERE");

        // Construct the request body
        //String requestBody = "{\"model\": \"gpt-3.5-turbo\", \"messages\": [{\"role\": \"user\", \"content\": \""+prompt+"\"}]}";
        String requestBody = "{\"prompt\": \"" + prompt + "\", \"max_tokens\": 100}";

        //System.out.println(requestBody);

        // Send the request
        connection.setDoOutput(true);
        OutputStream outputStream = connection.getOutputStream();
        outputStream.write(requestBody.getBytes(StandardCharsets.UTF_8));
        outputStream.flush();
        outputStream.close();

        // Get the response and extract the completion ID
        BufferedReader bufferedReader = new BufferedReader(new InputStreamReader(connection.getInputStream()));
        String inputLine;
        StringBuilder response = new StringBuilder();
        while ((inputLine = bufferedReader.readLine()) != null) {
            response.append(inputLine);
        }
        bufferedReader.close();

        String responseRaw = response.toString();
        int indexStart = responseRaw.indexOf("\"content\":\"") + "\"content\":\"".length();

        if(indexStart == -1) {
            return "Something went wrong getting the GPT response...";
        }

        responseRaw = responseRaw.substring(indexStart);
        int indexEnd = responseRaw.indexOf("\"},");
        responseRaw = responseRaw.substring(0,indexEnd);
        return responseRaw;


        /*
        String completionId = extractCompletionId(response.toString());

        // Make a GET request to get the generated response
        url = new URL(API_URL + "/" + completionId);
        connection = (HttpURLConnection) url.openConnection();
        connection.setRequestMethod("GET");
        //connection.setRequestProperty("Authorization", "Bearer " + API_KEY);

        // Get the response
        bufferedReader = new BufferedReader(new InputStreamReader(connection.getInputStream()));
        response = new StringBuilder();
        while ((inputLine = bufferedReader.readLine()) != null) {
            response.append(inputLine);
        }
        bufferedReader.close();

        // Extract the generated response from the JSON
        int start = response.indexOf("\"text\": \"") + 9;
        int end = response.indexOf("\"", start);
        String generatedResponse = response.substring(start, end);

        return generatedResponse;
         */
    }

    private static String extractCompletionId(String response) {
        Pattern pattern = Pattern.compile("\"id\": \"(.*?)\"");
        Matcher matcher = pattern.matcher(response);
        if (matcher.find()) {
            return matcher.group(1);
        } else {
            throw new RuntimeException("Unable to extract completion ID from response: " + response);
        }
    }
    public static String ArrayToString(String[] args) {
        String f = "";
        for(String s : args) {
            f = f + s + " ";
        }
        return f;
    }

    public static String[] splitter(String s) {

        String[] commandArray;
        if(useLocal) {
            commandArray = s.split(Pattern.quote("\n"));
        } else {
            commandArray = s.split(Pattern.quote("\\n"));
        }

        for (int i = 0; i < commandArray.length; i++) {
            if (commandArray[i].equals(" ")) {
                commandArray[i] = "";
                continue;
            }

            commandArray[i] = commandArray[i].replaceAll("^[0-9]+\\.\\s*", "");
            commandArray[i] = formatMinecraftCommand(commandArray[i]);

            commandArray[i] = commandArray[i].trim();


            if (commandArray[i].startsWith("/")) {
                commandArray[i] = commandArray[i].substring(0);
            }
            if (commandArray[i].startsWith("- /")) {
                commandArray[i] = commandArray[i].substring(2);
            }


        }

        System.out.println(Arrays.toString(commandArray));

        return commandArray;
    }
    public static String formatMinecraftCommand(String command) {
        command = command.trim();
        if (command.startsWith("/")) {
            command = command.substring(1);
        }
        return command;
    }


    public static String RequestGPTFromLocal(String prompt) {
        String hostName = "127.0.0.1";
        int portNumber = 23484;

        try (Socket socket = new Socket(hostName, portNumber);
             PrintWriter out = new PrintWriter(socket.getOutputStream(), true);
             BufferedReader in = new BufferedReader(new InputStreamReader(socket.getInputStream()))) {
            out.println(prompt);

            // Wait for a response from the server
            String response = "";
            boolean still = true;
            while(still == true) {
                String line = in.readLine();
                if(line == null || line == "") {still = false; break;}
                else {response = response +"\n"+ line;}
            }
            return response;
        } catch (UnknownHostException e) {
            System.err.println("Don't know about host " + hostName);
        } catch (IOException e) {
            System.err.println("Couldn't get I/O for the connection to " + hostName);
        }


        return "";
    }

}
